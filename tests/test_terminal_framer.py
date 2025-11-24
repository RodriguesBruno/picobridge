import src.terminal_framer as tf


def setup_time(monkeypatch, start_ms=1000):
    state = {'ms': start_ms}

    def ticks_ms():
        return state['ms']

    def ticks_diff(a, b):
        return a - b

    monkeypatch.setattr(tf.time, "ticks_ms", ticks_ms, raising=False)
    monkeypatch.setattr(tf.time, "ticks_diff", ticks_diff, raising=False)

    return state


def test_apply_backspaces_simple():
    assert tf.apply_backspaces("abc\bde\b\bf") == "abf"
    # single backspace removes previous char
    assert tf.apply_backspaces("a\b") == ""


def test_normalize_newlines():
    s = "line1\r\nline2\rline3\n"
    assert tf.normalize_newlines(s) == "line1\nline2\nline3\n"


def test_frames_emit_complete_lines(monkeypatch):
    state = setup_time(monkeypatch)
    fr = tf.TerminalFramer(idle_flush_ms=50)

    frames = fr.process_chunk(b"hello\nworld\n")
    assert frames == ["hello\n", "world\n"]


def test_pager_token_emitted_immediately(monkeypatch):
    state = setup_time(monkeypatch)
    fr = tf.TerminalFramer(idle_flush_ms=50)

    # token appears inside stream without newline; before text should be emitted as a line
    frames = fr.process_chunk(b"prefixUsername:rest")
    # "prefix" should be emitted as a line (newline inserted), then token on its own line
    assert frames == ["prefix\n", "Username:\n"]
    # remainder ("rest") stays in accumulator until newline/idle
    assert fr._line_accum.startswith("rest")


def test_utf8_split_across_chunks(monkeypatch):
    state = setup_time(monkeypatch)
    fr = tf.TerminalFramer(idle_flush_ms=50)

    # '✓' is 3-byte utf-8 (b'\xe2\x9c\x93')
    first = b'\xe2\x9c'      # incomplete
    second = b'\x93\n'       # completes char and a newline

    frames1 = fr.process_chunk(first)
    assert frames1 == []  # incomplete sequence yields no frames yet

    frames2 = fr.process_chunk(second)
    # Should produce the character plus newline as a single framed line
    assert frames2 == ["✓\n"]


def test_flush_idle_emits_partial_after_timeout(monkeypatch):
    state = setup_time(monkeypatch, start_ms=1000)
    fr = tf.TerminalFramer(idle_flush_ms=50)

    # feed partial text (no newline)
    frames = fr.process_chunk(b"partial")
    assert frames == []  # no newline => no frames

    # advance time past idle threshold
    state['ms'] += 100
    flushed = fr.flush_idle()
    assert flushed == ["partial"]
    # accumulator cleared after flush
    assert fr._line_accum == ""


def test_process_multiple_operations(monkeypatch):
    state = setup_time(monkeypatch)
    fr = tf.TerminalFramer(idle_flush_ms=20)

    # mix of data: line, token, partial
    payload = b"one\ntwo\nprompt--More--partial"
    frames = fr.process_chunk(payload)
    # Expect lines 'one\n', 'two\n', then '--More--\n' and 'prompt\n' (before token)
    # Note: depending on token placement this checks token behavior and ordering
    assert "--More--\n" in frames
