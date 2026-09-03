from dataclasses import dataclass

from .contracts import STTProvider, TranscriptEvent
from .errors import ProviderUnavailable


@dataclass(frozen=True, slots=True)
class STTHealth:
    active_provider: str | None
    degraded: bool
    last_failure: str | None


class FailoverSTTProvider(STTProvider):
    """Own Speechmatics-first STT failover without replaying accepted audio."""

    name = "speechmatics-deepgram-failover"

    def __init__(self, primary: STTProvider, fallback: STTProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self._active: STTProvider | None = None
        self._started: dict[int, STTProvider] = {}
        self._turn_id: int | None = None
        self._audio_accepted = False
        self._fallback_pending = False
        self._last_failure: str | None = None

    @property
    def health(self) -> STTHealth:
        active_name = getattr(self._active, "name", None)
        return STTHealth(
            active_provider=active_name,
            degraded=self._active is self.fallback or self._last_failure is not None,
            last_failure=self._last_failure,
        )

    async def start(self) -> None:
        try:
            await self._start_provider(self.primary)
            self._active = self.primary
        except Exception as exc:
            self._record_failure(self.primary, exc)
            await self._cleanup(self.primary)
            try:
                await self._start_provider(self.fallback)
                self._active = self.fallback
            except Exception as fallback_exc:
                self._record_failure(self.fallback, fallback_exc)
                await self._cleanup(self.fallback)
                self._active = None
                raise ProviderUnavailable("no STT provider could start") from fallback_exc

    async def begin_turn(self, turn_id: int) -> None:
        if self._fallback_pending:
            await self._activate_fallback()
            self._fallback_pending = False
        if self._active is None:
            raise ProviderUnavailable("no active STT provider")
        self._turn_id = turn_id
        self._audio_accepted = False
        try:
            await self._active.begin_turn(turn_id)
        except Exception as exc:
            failed = self._active
            self._record_failure(failed, exc)
            if failed is not self.primary:
                raise ProviderUnavailable("fallback STT could not begin turn") from exc
            await self._activate_fallback()
            await self._active.begin_turn(turn_id)

    async def stream_audio(self, pcm: bytes) -> None:
        if self._active is None:
            raise ProviderUnavailable("no active STT provider")
        if self._turn_id is None:
            try:
                await self._active.stream_audio(pcm)
                return
            except Exception as exc:
                failed = self._active
                self._record_failure(failed, exc)
                if failed is self.primary:
                    await self._activate_fallback()
                    await self._active.stream_audio(pcm)
                    return
                await self._cleanup(failed)
                self._active = None
                raise ProviderUnavailable("continuous STT audio failed") from exc
        had_accepted_audio = self._audio_accepted
        try:
            await self._active.stream_audio(pcm)
            self._audio_accepted = True
        except Exception as exc:
            failed = self._active
            self._record_failure(failed, exc)
            if not had_accepted_audio and failed is self.primary:
                turn_id = self._turn_id
                await self._activate_fallback()
                await self._active.begin_turn(turn_id)
                await self._active.stream_audio(pcm)
                self._audio_accepted = True
                return
            await self._cleanup(failed)
            self._fallback_pending = failed is self.primary
            self._turn_id = None
            self._audio_accepted = False
            raise ProviderUnavailable("current STT turn failed; audio was not replayed") from exc

    async def partial_text(self) -> TranscriptEvent | None:
        if self._active is None:
            return None
        return await self._active.partial_text()

    async def final_text(self, turn_id: int | None = None) -> TranscriptEvent:
        if self._active is None or self._turn_id is None:
            raise ProviderUnavailable("STT turn has not started")
        selected_turn_id = self._turn_id if turn_id is None else turn_id
        if selected_turn_id != self._turn_id:
            raise ProviderUnavailable("requested transcript turn is not active")
        try:
            return await self._active.final_text(selected_turn_id)
        except Exception as exc:
            failed = self._active
            self._record_failure(failed, exc)
            await self._cleanup(failed)
            self._fallback_pending = failed is self.primary
            raise ProviderUnavailable("current STT turn failed; audio was not replayed") from exc
        finally:
            self._turn_id = None
            self._audio_accepted = False

    async def stop(self) -> None:
        for provider in tuple(self._started.values()):
            await self._cleanup(provider)
        self._active = None
        self._turn_id = None
        self._audio_accepted = False
        self._fallback_pending = False

    async def _activate_fallback(self) -> None:
        if self._active is self.fallback and id(self.fallback) in self._started:
            return
        if self._active is not None and id(self._active) in self._started:
            await self._cleanup(self._active)
        try:
            await self._start_provider(self.fallback)
        except Exception as exc:
            self._record_failure(self.fallback, exc)
            await self._cleanup(self.fallback)
            self._active = None
            raise ProviderUnavailable("fallback STT could not start") from exc
        self._active = self.fallback

    async def _start_provider(self, provider: STTProvider) -> None:
        await provider.start()
        self._started[id(provider)] = provider

    async def _cleanup(self, provider: STTProvider) -> None:
        try:
            await provider.stop()
        except Exception:
            pass
        self._started.pop(id(provider), None)

    def _record_failure(self, provider: STTProvider, exc: Exception) -> None:
        self._last_failure = f"{getattr(provider, 'name', 'unknown')}: {type(exc).__name__}"


__all__ = ["FailoverSTTProvider", "STTHealth"]
