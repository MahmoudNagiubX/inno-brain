"""Run non-interactive, credential-gated Phase 3 provider smoke checks."""

import argparse
import asyncio
import wave
from pathlib import Path

from innobrain.providers.registry import ProviderRegistry

DEFAULT_WAV = Path(__file__).parents[2] / "recordings" / "phase1" / "laptop_mic_egyptian.wav"
DEFAULT_AZURE_WAV = Path(__file__).parents[2] / "artifacts" / "phase3" / "azure_shakir_smoke.wav"
PROVIDERS = ("speechmatics", "deepgram", "groq", "azure")


def _configured(provider: str) -> bool:
    return next(
        item for item in ProviderRegistry().availability() if item.name == provider
    ).configured


def _read_pcm_chunks(path: Path, chunk_bytes: int = 3200) -> list[bytes]:
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != 16000
        ):
            raise ValueError("smoke WAV must be mono 16-bit PCM at 16000 Hz")
        data = source.readframes(source.getnframes())
    return [data[index : index + chunk_bytes] for index in range(0, len(data), chunk_bytes)]


async def _smoke_stt(provider_name: str, wav_path: Path) -> str:
    if provider_name == "speechmatics":
        from innobrain.providers.speechmatics_stt import SpeechmaticsSTTProvider

        provider = SpeechmaticsSTTProvider()
    else:
        from innobrain.providers.deepgram_stt import DeepgramSTTProvider

        provider = DeepgramSTTProvider()
    await provider.start()
    try:
        for chunk in _read_pcm_chunks(wav_path):
            await provider.stream_audio(chunk)
        result = await provider.final_text()
        return result.text
    finally:
        await provider.stop()


async def _smoke_groq() -> str:
    from innobrain.providers import ChatMessage
    from innobrain.providers.groq_llm import GroqLLMProvider

    provider = GroqLLMProvider()
    parts = [
        part
        async for part in provider.stream(
            [
                ChatMessage("system", "Answer only from the supplied event evidence."),
                ChatMessage("user", "Where is the booth?"),
                ChatMessage(
                    "user",
                    "<event_evidence> Innovatronics Booth is in Expo A12. "
                    "</event_evidence>",
                ),
            ],
            tools=(),
            context=None,
        )
    ]
    return "".join(parts)


async def _smoke_azure(output_path: Path) -> int:
    from innobrain.providers.azure_tts import AzureTTSProvider

    provider = AzureTTSProvider()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = [
        chunk
        async for chunk in provider.stream(
            "أهلاً بيكم، أنا InnoBrain وموجود هنا عشان أساعدكم في الإيفنت."
        )
    ]
    pcm = b"".join(chunk.data for chunk in chunks)
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(pcm)
    with wave.open(str(output_path), "rb") as check:
        if (check.getnchannels(), check.getsampwidth(), check.getframerate()) != (1, 2, 16000):
            raise ValueError("Azure smoke output is not 16 kHz mono PCM16")
        return check.getnframes()


def _run(provider: str, wav_path: Path, azure_path: Path) -> None:
    if not _configured(provider):
        print(f"PROVIDER={provider} STATUS=SKIPPED_MISSING_CREDENTIAL")
        return
    try:
        if provider in {"speechmatics", "deepgram"}:
            result = asyncio.run(_smoke_stt(provider, wav_path))
            print(f"PROVIDER={provider} STATUS=PASS TRANSCRIPT_CHARS={len(result)}")
        elif provider == "groq":
            result = asyncio.run(_smoke_groq())
            print(f"PROVIDER={provider} STATUS=PASS RESPONSE_CHARS={len(result)}")
        else:
            frames = asyncio.run(_smoke_azure(azure_path))
            print(f"PROVIDER={provider} STATUS=PASS WAV_FRAMES={frames}")
    except Exception as exc:
        print(f"PROVIDER={provider} STATUS=ERROR ERROR_TYPE={type(exc).__name__}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--provider", choices=PROVIDERS)
    selection.add_argument("--all-configured", action="store_true")
    parser.add_argument("--wav", type=Path, default=DEFAULT_WAV)
    parser.add_argument("--azure-output", type=Path, default=DEFAULT_AZURE_WAV)
    args = parser.parse_args()
    providers = PROVIDERS if args.all_configured else (args.provider,)
    if (
        any(provider in {"speechmatics", "deepgram"} for provider in providers)
        and not args.wav.is_file()
    ):
        raise SystemExit(f"missing STT smoke WAV: {args.wav}")
    for provider in providers:
        try:
            _run(provider, args.wav, args.azure_output)
        except Exception as exc:
            raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
