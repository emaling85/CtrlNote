"""
Автотесты записи и расшифровки голоса (без реального микрофона, где возможно).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from voice import SAMPLE_RATE, save_wav


class VoiceHelperTests(unittest.TestCase):
    def test_save_wav(self) -> None:
        audio = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = save_wav(audio, Path(tmp) / "t.wav")
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 44)


if __name__ == "__main__":
    unittest.main()
