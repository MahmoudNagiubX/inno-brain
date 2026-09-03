from typing import TYPE_CHECKING, Any

from innobrain.wake.router import WakeAudioRouter

if TYPE_CHECKING:
    from innobrain.attention.contracts import AttentionState
    from innobrain.attention.controller import AttentionController


class WakeAttentionBridge:
    """One-stream audio bridge connecting PCM capture to WakeAudioRouter and AttentionController.

    Guarantees:
    - Every PCM chunk is routed once through WakeAudioRouter.
    - Sleeping chunks remain local and are never sent downstream to STT or VAD/Smart Turn.
    - On canonical wake ('heyino'), attention enters ENGAGED and only the current
      detection/continuation chunk is forwarded downstream.
    - In ENGAGED and FOLLOWUP_WINDOW, incoming chunks feed the downstream VAD/STT path.
    - Preserves same-breath handoff metadata on attention controller.
    - Ring buffer history is never forwarded to STT.
    """

    def __init__(
        self,
        router: WakeAudioRouter,
        attention: Any,
    ) -> None:
        self.router = router
        self.attention: AttentionController = attention
        # Ensure attention controller has router reference for mode synchronization
        if getattr(self.attention, "_router", None) is None:
            self.attention._router = router

    @property
    def mode(self) -> str:
        return self.router.mode.value

    @property
    def state(self) -> "AttentionState":
        return self.attention.state

    def process_chunk(self, chunk: bytes) -> bytes:
        """Route one PCM chunk from the capture stream.

        Returns downstream PCM (current/continuation chunk or engaged streaming audio)
        or b"" if sleeping and no canonical wake word was detected.
        """
        if not chunk:
            return b""

        # Check follow-up / max session timers before routing incoming chunk
        self.attention.check_timeouts()

        output = self.router.route_pcm(chunk)

        if output.detection is not None:
            # Canonical wake detected: engage attention session
            self.attention.on_wake_detected(
                output.detection,
                continuation_pcm=output.downstream_pcm,
            )
            return output.downstream_pcm

        if self.attention.is_engaged:
            # In ENGAGED or FOLLOWUP_WINDOW: stream directly downstream
            return output.downstream_pcm

        # In SLEEPING without detection: suppress audio from STT/VAD
        return b""

    def __call__(self, chunk: bytes) -> bytes:
        return self.process_chunk(chunk)

    def reset(self) -> None:
        """Reset internal buffers and state for both router and attention."""
        self.router.reset()
        self.attention.reset()

    def close(self) -> None:
        """Close underlying router and reset attention."""
        self.router.close()
        self.attention.reset()


__all__ = ["WakeAttentionBridge"]
