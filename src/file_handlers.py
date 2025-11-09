import ujson as json


def read_file_as_json(filename: str) -> dict:
    with open(filename, 'r') as f:
        return json.load(f)


def write_file_as_json(filename: str, data: dict) -> None:
    with open(filename, 'w') as f:
        json.dump(data, f)
