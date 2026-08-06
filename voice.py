"""
Запись с микрофона и расшифровка речи (Whisper).

Два режима: локально на компьютере или через OpenAI в интернете.
"""

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

from config import APP_DIR, load_config

# Частота и каналы записи — как ожидает Whisper
SAMPLE_RATE = 16_000
CHANNELS = 1

# Кэш загруженной модели Whisper (одна на процесс)
_model_lock = threading.Lock()
_model = None
_model_name: str | None = None

ProgressCallback = Callable[[str], None]


@dataclass
class RecordingResult:
    """Результат: распознанный текст и (опционально) путь к wav."""

    text: str
    wav_path: Path | None


class MicRecorder:
    """Записывает звук с микрофона по умолчанию (моно)."""

    def __init__(self) -> None:
        self._frames: list = []
        self._stream = None
        self.recording = False

    def start(self) -> None:
        """Начинает запись в фоне."""
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

    def stop(self):
        """Останавливает запись и возвращает массив сэмплов."""
        import numpy as np

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


def save_wav(audio, path: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    """Сохраняет запись в WAV-файл на диск."""
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return path


def audio_to_wav_bytes(audio, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Готовит WAV в памяти (для отправки в OpenAI)."""
    import numpy as np

    buf = io.BytesIO()
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def normalize_audio(audio):
    """Усиливает тихую запись, чтобы Whisper лучше распознал речь."""
    import numpy as np

    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak < 1e-5:
        return audio.astype(np.float32, copy=False)
    # Trim relative to this clip's level (absolute 0.01 kills quiet mics).
    energy = np.convolve(np.abs(audio), np.ones(800) / 800, mode="same")
    mask = energy > max(peak * 0.08, 1e-4)
    if np.any(mask):
        idx = np.where(mask)[0]
        audio = audio[idx[0] : idx[-1] + 1]
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 1e-5:
        return audio.astype(np.float32, copy=False)
    gain = min(0.9 / peak, 80.0)
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


def model_likely_cached(model_size: str) -> bool:
    """Грубая проверка: скачана ли уже локальная модель Whisper."""
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    marker = f"models--Systran--faster-whisper-{model_size}"
    return (hub / marker).exists()


def _get_model(model_size: str, on_progress: ProgressCallback | None = None):
    """Загружает (или берёт из кэша) локальную модель Whisper."""
    global _model, _model_name
    with _model_lock:
        if _model is not None and _model_name == model_size:
            return _model

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        cached = model_likely_cached(model_size)
        if on_progress:
            if cached:
                on_progress("Loading model…")
            else:
                on_progress("Downloading model…")

        from faster_whisper import WhisperModel

        # System SOCKS proxies (VPN) break huggingface downloads without PySocks.
        # Prefer local cache — never hit the network when the model is already there.
        try:
            _model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                local_files_only=cached,
            )
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            if "SOCKS" in err or "Proxy" in err or "proxy" in err:
                raise RuntimeError(
                    "Network proxy blocked Whisper model access. "
                    "Disable the system SOCKS/VPN proxy for CtrlNote, "
                    "or install PySocks (pip install PySocks)."
                ) from exc
            if cached:
                # Cache folder present but incomplete — retry online once.
                if on_progress:
                    on_progress("Downloading model…")
                try:
                    _model = WhisperModel(
                        model_size, device="cpu", compute_type="int8"
                    )
                except Exception as exc2:  # noqa: BLE001
                    err2 = str(exc2)
                    if "SOCKS" in err2 or "proxy" in err2.lower():
                        raise RuntimeError(
                            "Network proxy blocked Whisper model download. "
                            "Disable the system SOCKS/VPN proxy temporarily."
                        ) from exc2
                    raise
            else:
                raise
        _model_name = model_size
        if on_progress:
            on_progress("Transcribing…")
        return _model


def transcribe_local(
    audio,
    language: str = "en",
    model_size: str = "small",
    on_progress: ProgressCallback | None = None,
) -> str:
    """Transcribe speech locally with faster-whisper."""
    if audio.size == 0:
        return ""
    audio = normalize_audio(audio)
    # ~0.15s minimum — short notes should still work
    if audio.size < SAMPLE_RATE // 6:
        return ""

    model = _get_model(model_size, on_progress=on_progress)
    if on_progress:
        on_progress("Transcribing…")

    lang = (language or "").strip().lower()
    if lang in {"", "auto", "detect"}:
        lang_arg = None
    else:
        lang_arg = lang.split("-")[0]

    segments, _info = model.transcribe(
        audio,
        language=lang_arg,
        task="transcribe",
        beam_size=1,
        best_of=1,
        vad_filter=False,
        condition_on_previous_text=False,
        without_timestamps=True,
        temperature=0.0,
        compression_ratio_threshold=2.8,
        # Higher = keep more segments (0.35 was discarding quiet speech as silence).
        no_speech_threshold=0.6,
    )
    parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    text = " ".join(parts).strip()
    return " ".join(text.split())


def transcribe_openai(
    audio,
    api_key: str,
    language: str = "en",
    on_progress: ProgressCallback | None = None,
) -> str:
    """Отправляет аудио в OpenAI Whisper API и возвращает текст."""
    if audio.size == 0:
        return ""
    audio = normalize_audio(audio)
    if audio.size < SAMPLE_RATE // 4:
        return ""
    if not api_key.strip():
        raise ValueError("OpenAI API key is missing")

    if on_progress:
        on_progress("Sending to OpenAI…")

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
    """Папка для сохранённых wav-записей голоса."""
    path = APP_DIR / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def process_recording(
    audio,
    *,
    save_audio: bool = True,
    language: str = "en",
    model_size: str = "small",
    engine: str = "local",
    openai_api_key: str = "",
    on_progress: ProgressCallback | None = None,
) -> RecordingResult:
    """Полный цикл: нормализация → (опц.) сохранить wav → расшифровать."""
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
    audio,
    on_done: Callable[[RecordingResult], None],
    on_error: Callable[[BaseException], None],
    on_progress: ProgressCallback | None = None,
) -> None:
    """Запускает расшифровку в фоне, чтобы окно не зависало."""
    config = load_config()
    language = str(config.get("voice_language", "en") or "en")
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
