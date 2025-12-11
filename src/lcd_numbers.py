zero = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 0, 1),
    (1, 0, 1),
    (1, 1, 1)
)

one = (
    (0, 1, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 1, 0),
    (1, 1, 1)
)

two = (
    (1, 1, 1),
    (0, 0, 1),
    (1, 1, 1),
    (1, 0, 0),
    (1, 1, 1)
)

three = (
    (1, 1, 1),
    (0, 0, 1),
    (0, 1, 1),
    (0, 0, 1),
    (1, 1, 1)
)

four = (
    (1, 0, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 0, 1),
    (0, 0, 1)
)

five = (
    (1, 1, 1),
    (1, 0, 0),
    (1, 1, 1),
    (0, 0, 1),
    (1, 1, 1)
)

six = (
    (1, 1, 0),
    (1, 0, 0),
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 1)
)

seven = (
    (1, 1, 1),
    (1, 0, 1),
    (0, 0, 1),
    (0, 0, 1),
    (0, 0, 1)
)

eight = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 1)
)

nine = (
    (1, 1, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 0, 1),
    (0, 0, 1)
)


def make_matrix(val: int) -> tuple:
    if val == 0:
        return zero
    if val == 1:
        return one
    if val == 2:
        return two
    if val == 3:
        return three
    if val == 4:
        return four
    if val == 5:
        return five
    if val == 6:
        return six
    if val == 7:
        return seven
    if val == 8:
        return eight
    if val == 9:
        return nine


def c_gen(x: int, y: int, side: int) -> list:
    result = []
    for val in range(5):
        if val == 0:
            result.append([(x - side - int(side / 2), y, side, side, 1),
                           (x - int(side / 2) + 1, y, side, side, 1),
                           (x + int(side / 2) + 2, y, side, side, 1)]
                          )
        else:
            result.append([(x - side - int(side / 2), y + side * val + val, side, side, 1),
                           (x - int(side / 2) + 1, y + side * val + val, side, side, 1),
                           (x + int(side / 2) + 2, y + side * val + val, side, side, 1)]
                          )

    return result


def make_char(matrix, x, y, side) -> tuple:
    result = []
    for row, lines in enumerate(matrix):
        for column, line in enumerate(lines):
            if line:
                result.append(c_gen(x, y, side)[row][column])

    return tuple(result)


def get_char(val: int, x: int = 64, y: int = 10, side: int = 8) -> tuple:
    matrix = make_matrix(val)
    return make_char(matrix, x, y, side)