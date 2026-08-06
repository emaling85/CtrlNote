"""Microphone recording and Whisper transcription (local + OpenAI)."""

from __future__ import annotations

import io
import json
import os
import threading
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib import error, request

import numpy as np

from config import APP_DIR, load_config

SAMPLE_RATE = 16_000
CHANNELS = 1

_model_lock = threading.Lock()
_model = None
_model_name: str | None = None

ProgressCallback = Callable[[str], None]


@dataclass
class RecordingResult:
    text: str
    wav_path: Path | None


class MicRecorder:
    """Record mono float32 audio from the default input device."""

    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._stream = None
        self.recording = False

    def start(self) -> None:
        import sounddevice as sd

        if self.recording:
            return
        self._frames = []
        self.recording = True

        def callback(indata, frames, time, status) -> None:  # noqa: ANN001, ARG001
            if self.recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        self.recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            return np.zeros((0,), dtype=np.float32)
        audio = np.concatenate(self._frames, axis=0)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio.astype(np.float32, copy=False)


def save_wav(audio: np.ndarray, path: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return path


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Boost quiet mic input to a usable level for Whisper."""
    if audio.size == 0:
        return audio
    energy = np.convolve(np.abs(audio), np.ones(800) / 800, mode="same")
    mask = energy > 0.01
    if np.any(mask):
        idx = np.where(mask)[0]
        audio = audio[idx[0] : idx[-1] + 1]
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 1e-4:
        return audio.astype(np.float32, copy=False)
    gain = min(0.85 / peak, 12.0)
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


def model_likely_cached(model_size: str) -> bool:
    """Best-effort check whether faster-whisper model files already exist."""
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    marker = f"models--Systran--faster-whisper-{model_size}"
    return (hub / marker).exists()


def _get_model(model_size: str, on_progress: ProgressCallback | None = None):
    global _model, _model_name
    with _model_lock:
        if _model is not None and _model_name == model_size:
            return _model

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        if on_progress:
            if model_likely_cached(model_size):
                on_progress("Загрузка модели…")
            else:
                on_progress("Скачивание модели…")

        from faster_whisper import WhisperModel

        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _model_name = model_size
        if on_progress:
            on_progress("Расшифровка…")
        return _model


def transcribe_local(
    audio: np.ndarray,
    language: str = "ru",
    model_size: str = "small",
    on_progress: ProgressCallback | None = None,
) -> str:
    if audio.size == 0:
        return ""
    audio = normalize_audio(audio)
    if audio.size < SAMPLE_RATE // 4:
        return ""

    model = _get_model(model_size, on_progress=on_progress)
    if on_progress:
        on_progress("Расшифровка…")
    segments, _info = model.transcribe(
        audio,
        language=language or None,
        task="transcribe",
        beam_size=5,
        best_of=5,
        patience=1.0,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        condition_on_previous_text=False,
        without_timestamps=True,
        temperature=0.0,
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
    )
    parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    text = " ".join(parts).strip()
    return " ".join(text.split())


def transcribe_openai(
    audio: np.ndarray,
    api_key: str,
    language: str = "ru",
    on_progress: ProgressCallback | None = None,
) -> str:
    if audio.size == 0:
        return ""
    audio = normalize_audio(audio)
    if audio.size < SAMPLE_RATE // 4:
        return ""
    if not api_key.strip():
        raise ValueError("Не указан OpenAI API key")

    if on_progress:
        on_progress("Отправка в OpenAI…")

    wav_bytes = audio_to_wav_bytes(audio)
    boundary = "----CtrlNoteFormBoundary7MA4YWxkTrZu0gW"
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    add_field("model", "whisper-1")
    if language:
        add_field("language", language.split("-")[0])

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        b'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
        b"Content-Type: audio/wav\r\n\r\n"
    )
    body.extend(wav_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=bytes(body),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Whisper error {exc.code}: {detail}") from exc

    text = str(payload.get("text", "")).strip()
    return " ".join(text.split())


def recordings_dir() -> Path:
    path = APP_DIR / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def process_recording(
    audio: np.ndarray,
    *,
    save_audio: bool = True,
    language: str = "ru",
    model_size: str = "small",
    engine: str = "local",
    openai_api_key: str = "",
    on_progress: ProgressCallback | None = None,
) -> RecordingResult:
    audio = normalize_audio(audio)
    wav_path: Path | None = None
    if save_audio and audio.size > 0:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        wav_path = save_wav(audio, recordings_dir() / f"voice-{stamp}.wav")

    if engine == "openai":
        text = transcribe_openai(
            audio,
            api_key=openai_api_key,
            language=language,
            on_progress=on_progress,
        )
    else:
        text = transcribe_local(
            audio,
            language=language,
            model_size=model_size,
            on_progress=on_progress,
        )
    return RecordingResult(text=text, wav_path=wav_path)


def transcribe_in_background(
    audio: np.ndarray,
    on_done: Callable[[RecordingResult], None],
    on_error: Callable[[BaseException], None],
    on_progress: ProgressCallback | None = None,
) -> None:
    config = load_config()
    language = str(config.get("voice_language", "ru") or "ru")
    model_size = str(config.get("whisper_model", "small") or "small")
    save_audio = bool(config.get("save_voice_audio", False))
    engine = str(config.get("voice_engine", "local") or "local")
    api_key = str(config.get("openai_api_key", "") or "")

    def worker() -> None:
        try:
            result = process_recording(
                audio,
                save_audio=save_audio,
                language=language,
                model_size=model_size,
                engine=engine,
                openai_api_key=api_key,
                on_progress=on_progress,
            )
            on_done(result)
        except BaseException as exc:  # noqa: BLE001
            on_error(exc)

    threading.Thread(target=worker, daemon=True, name="CtrlNoteWhisper").start()
