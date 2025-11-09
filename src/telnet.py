
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240

TELNET_INIT: bytes = bytes([
    IAC, DO, 1,  # DO ECHO (ask client to stop echoing)
    IAC, WILL, 1,  # WILL ECHO (we agree to handle echo if needed)
    IAC, WILL, 3,  # WILL SUPPRESS-GO-AHEAD
    IAC, DO, 34,  # DO LINEMODE
    IAC, SB, 34, 1, 0, IAC, SE  # SB LINEMODE MODE 0
])


def telnet_negotiation(buf: bytes) -> tuple[bytes, bytes]:
    out, resp = bytearray(), bytearray()
    i, n = 0, len(buf)

    while i < n:
        b = buf[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue

        if i + 1 >= n:
            break

        cmd = buf[i + 1]
        if cmd in (DO, DONT, WILL, WONT):
            if i + 2 >= n:
                break

            opt = buf[i + 2]
            if cmd == DO:
                resp += bytes([IAC, WONT, opt])
            elif cmd == WILL:
                resp += bytes([IAC, DONT, opt])

            i += 3

        elif cmd == SB:
            i += 2
            while i < n - 1 and not (buf[i] == IAC and buf[i + 1] == SE):
                i += 1

            i += 2 if i < n - 1 else 0

        elif cmd == IAC:
            out.append(IAC)
            i += 2
        else:
            i += 2

    return bytes(out), bytes(resp)
