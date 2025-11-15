import time

def apply_backspaces(s: str) -> str:
    out = []
    for ch in s:
        if ch == '\b':
            if out:
                out.pop()
        else:
            out.append(ch)

    return ''.join(out)

def normalize_newlines(s: str) -> str:
    s = s.replace('\r\n', '\n')
    s = s.replace('\r', '\n')

    return s


class TerminalFramer:
    def __init__(self, idle_flush_ms: int = 150, flush_tokens = None) -> None:
        self._utf8_tail: bytes = b''
        self._line_accum: str = ''
        self._last_rx_ms = time.ticks_ms()
        self._idle_flush_ms = idle_flush_ms
        self._flush_tokens = flush_tokens or ('Username:', 'Password:', 'login:', '--More--')


    def _utf8_feed(self, chunk: bytes) -> str:
        b = self._utf8_tail + chunk
        try:
            s = b.decode()
            self._utf8_tail = b''
            return s

        except Exception:
            # Try stripping 1..3 tail bytes as incomplete sequence
            for keep in (1, 2, 3):
                if len(b) > keep:
                    try:
                        s = b[:-keep].decode()
                        self._utf8_tail = b[-keep:]
                        return s
                    except Exception:
                        pass
            # nothing decodes -> keep all bytes as tail
            self._utf8_tail = b

            return ''

    def _split_on_pager_or_prompt(self, text: str) -> tuple:
        first_idx = -1
        first_tok = None
        for tok in self._flush_tokens:
            idx = text.find(tok)
            if idx != -1 and (first_idx == -1 or idx < first_idx):
                first_idx = idx
                first_tok = tok

        if first_idx == -1:
            return text, None, ''
        prefix = text[:first_idx]
        suffix = text[first_idx + len(first_tok):]

        return prefix, first_tok, suffix

    def _frames_from_text(self, s: str) -> list[str]:
        frames: list[str] = []
        s = apply_backspaces(s)
        s = normalize_newlines(s)

        self._line_accum += s

        # emit complete newline-terminated lines
        while True:
            nl = self._line_accum.find('\n')
            if nl == -1:
                break
            line = self._line_accum[:nl + 1]
            frames.append(line)
            self._line_accum = self._line_accum[nl + 1:]

        # detect pager/prompt tokens in remaining partial and emit them immediately
        while True:
            if not self._line_accum:
                break

            before, tok, after = self._split_on_pager_or_prompt(self._line_accum)
            if tok is None:
                break

            if before:
                frames.append(before + ('\n' if not before.endswith('\n') else ''))

            frames.append(tok + '\n')
            self._line_accum = after

        return frames

    def process_chunk(self, chunk: bytes) -> list[str]:
        """Feed a raw UART chunk, returns list of frames (strings)."""
        self._last_rx_ms = time.ticks_ms()
        decoded = self._utf8_feed(chunk)
        if not decoded:
            return []

        return self._frames_from_text(decoded)

    def flush_idle(self) -> list[str]:
        """If idle and partial exists, emit it (to avoid stuck prompts)."""
        now = time.ticks_ms()
        if self._line_accum and time.ticks_diff(now, self._last_rx_ms) >= self._idle_flush_ms:
            frame = self._line_accum
            self._line_accum = ''
            return [frame]

        return []