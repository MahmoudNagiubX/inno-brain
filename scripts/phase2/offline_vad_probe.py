import asyncio
from pathlib import Path

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams, VADState

from innobrain.audio.io import read_pcm16_wav
from innobrain.config import load_all_configs

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RECORDING_PATH = REPOSITORY_ROOT / "recordings" / "phase1" / "laptop_mic_egyptian.wav"


async def probe() -> int:
    if not RECORDING_PATH.exists():
        print("OFFLINE_PHASE1_WAV_NOT_AVAILABLE")
        return 0

    samples, sample_rate_hz = read_pcm16_wav(RECORDING_PATH)
    if sample_rate_hz != 16000:
        raise ValueError(f"Expected 16 kHz WAV, got {sample_rate_hz} Hz")

    config = load_all_configs(REPOSITORY_ROOT).runtime
    vad = SileroVADAnalyzer(
        sample_rate=sample_rate_hz,
        params=VADParams(
            confidence=config.realtime.vad.confidence,
            start_secs=config.realtime.vad.start_secs,
            stop_secs=config.realtime.vad.stop_secs,
            min_volume=config.realtime.vad.min_volume,
        ),
    )
    vad.set_sample_rate(sample_rate_hz)
    speech_starts = 0
    speech_stops = 0
    previous_state = VADState.QUIET
    try:
        pcm = samples.tobytes()
        for offset in range(0, len(pcm) - 1023, 1024):
            state = await vad.analyze_audio(pcm[offset : offset + 1024])
            if previous_state is not VADState.SPEAKING and state is VADState.SPEAKING:
                speech_starts += 1
            if previous_state is not VADState.QUIET and state is VADState.QUIET:
                speech_stops += 1
            previous_state = state
    finally:
        await vad.cleanup()

    print(f"SPEECH_STARTS={speech_starts}")
    print(f"SPEECH_STOPS={speech_stops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(probe()))
