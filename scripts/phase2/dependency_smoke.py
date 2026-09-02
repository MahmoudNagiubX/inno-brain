import asyncio
from importlib.metadata import version

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer


async def main() -> int:
    installed = version("pipecat-ai")
    if installed != "1.8.1":
        raise RuntimeError(f"Expected pipecat-ai 1.8.1, got {installed}")

    vad = SileroVADAnalyzer(sample_rate=16000)
    smart_turn = LocalSmartTurnAnalyzerV3(cpu_count=1)

    try:
        print(f"PIPECAT_VERSION={installed}")
        print("SILERO_INIT_OK")
        print("SMART_TURN_V3_INIT_OK")
    finally:
        await vad.cleanup()
        await smart_turn.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
