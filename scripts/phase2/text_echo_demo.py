import asyncio

from innobrain.voice.state import ConversationState, ConversationStateMachine
from innobrain.voice.text_echo import echo_text_once


async def main() -> None:
    machine = ConversationStateMachine()
    machine.transition(ConversationState.LISTENING, "runtime_started")
    print(f"STATE: {machine.state.value}")

    while True:
        try:
            text = input("Egyptian text (Ctrl+C to stop): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            return

        previous_history_size = len(machine.history)
        result = await echo_text_once(text, machine)
        for transition in machine.history[previous_history_size:]:
            print(
                "STATE: "
                f"{transition.from_state.value} -> {transition.to_state.value} "
                f"({transition.reason})"
            )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
