from pathlib import Path

import numpy as np

from innobrain.audio.io import read_pcm16_wav, write_pcm16_wav


def test_write_and_read_pcm16_mono_wav_round_trip(tmp_path: Path) -> None:
    samples = np.array([-32768, -123, 0, 123, 32767], dtype=np.int16)
    path = tmp_path / "sample.wav"

    write_pcm16_wav(path, samples, sample_rate_hz=16000)

    restored, sample_rate = read_pcm16_wav(path)

    assert sample_rate == 16000
    np.testing.assert_array_equal(restored, samples)
