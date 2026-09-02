from .state import ConversationState, ConversationStateMachine


async def echo_text_once(
    text: str,
    machine: ConversationStateMachine,
) -> str:
    if machine.state is ConversationState.IDLE:
        machine.transition(ConversationState.LISTENING, "runtime_started")
    if machine.state is not ConversationState.LISTENING:
        raise RuntimeError("Text echo requires a listening conversation")

    machine.transition(ConversationState.THINKING, "text_received")
    machine.transition(ConversationState.SPEAKING, "echo_ready")
    machine.transition(ConversationState.LISTENING, "echo_finished")
    return f"ECHO: {text}"
