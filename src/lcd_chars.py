char_p = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 1),
    (1, 0, 0),
    (1, 0, 0)
)

char_i = (
    (0, 1, 0),
    (0, 1, 0),
    (0, 1, 0),
    (0, 1, 0),
    (0, 1, 0)
)

char_c = (
    (1, 1, 1),
    (1, 0, 0),
    (1, 0, 0),
    (1, 0, 0),
    (1, 1, 1)
)

char_o = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 0, 1),
    (1, 0, 1),
    (1, 1, 1)
)

char_b = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 0),
    (1, 0, 1),
    (1, 1, 1)
)

char_r = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 0),
    (1, 0, 1),
    (1, 0, 1)
)

char_d = (
    (1, 1, 0),
    (1, 0, 1),
    (1, 0, 1),
    (1, 0, 1),
    (1, 1, 0)
)

char_g = (
    (1, 1, 1),
    (1, 0, 0),
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 1)
)

char_e = (
    (1, 1, 1),
    (1, 0, 0),
    (1, 1, 0),
    (1, 0, 0),
    (1, 1, 1)
)

def make_str_matrix(value: str) -> tuple:
    if value == 'P':
        return char_p
    if value == 'I':
        return char_i
    if value == 'C':
        return char_c
    if value == 'O':
        return char_o
    if value == 'B':
        return char_b
    if value == 'R':
        return char_r
    if value == 'D':
        return char_d
    if value == 'G':
        return char_g
    if value == 'E':
        return char_e

    return char_e

def c_gen(x: int, y: int, side: int) -> list:
    result = []
    for val in range(5):
        if val == 0:
            result.append(
                [
                    (x - side - int(side / 2), y, side, side, 1),
                    (x - int(side / 2) + 1, y, side, side, 1),
                    (x + int(side / 2) + 2, y, side, side, 1)
                ]
            )
        else:
            result.append(
                [
                    (x - side - int(side / 2), y + side * val + val, side, side, 1),
                    (x - int(side / 2) + 1, y + side * val + val, side, side, 1),
                    (x + int(side / 2) + 2, y + side * val + val, side, side, 1)
                ]
            )

    return result


def make_char(matrix, x, y, side) -> tuple:
    result = []
    for row, lines in enumerate(matrix):
        for column, line in enumerate(lines):
            if line:
                result.append(c_gen(x, y, side)[row][column])

    return tuple(result)


def get_char(value: str, x: int = 64, y: int = 10, side: int = 8) -> tuple:
    matrix: tuple = make_str_matrix(value=value)

    return make_char(matrix, x, y, side)