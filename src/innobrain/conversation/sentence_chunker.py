import string

_BOUNDARIES = frozenset(".!?؟\n")


class SentenceChunker:
    def __init__(self, *, min_forced_chars: int = 80) -> None:
        if min_forced_chars < 1:
            raise ValueError("min_forced_chars must be positive")
        self.min_forced_chars = min_forced_chars
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        return self._drain()

    def flush(self) -> list[str]:
        if not self._buffer.strip():
            self._buffer = ""
            return []
        result = [self._buffer.strip()]
        self._buffer = ""
        return result

    def _drain(self) -> list[str]:
        emitted: list[str] = []
        while self._buffer:
            boundary = self._first_boundary()
            if boundary is not None:
                emitted.append(self._buffer[:boundary].strip())
                self._buffer = self._buffer[boundary:]
                continue
            if len(self._buffer) < self.min_forced_chars:
                break
            cut = self._buffer.rfind(" ", 0, self.min_forced_chars + 1)
            if cut <= 0:
                cut = self.min_forced_chars
            emitted.append(self._buffer[:cut].strip())
            self._buffer = self._buffer[cut:].lstrip()
        return [item for item in emitted if item]

    def _first_boundary(self) -> int | None:
        for index, character in enumerate(self._buffer):
            if character not in _BOUNDARIES:
                continue
            if character == ".":
                previous = self._buffer[index - 1] if index else ""
                following = self._buffer[index + 1] if index + 1 < len(self._buffer) else ""
                if previous in string.digits and following in string.digits:
                    continue
            return index + 1
        return None
