import os
import json


# def read_file_as_json(filename: str) -> dict:
#     with open(filename, 'r') as f:
#         return json.load(f)

def read_file_as_json(filename: str, default: dict | None = None) -> dict:
    if default is None:
        default = {}
    try:
        with open(filename, "r") as f:
            return json.load(f)

    except (OSError, ValueError):
        return json.loads(json.dumps(default))

def write_file_as_json(filename: str, data: dict) -> None:
    tmp = filename + ".tmp"
    bak = filename + ".bak"

    with open(tmp, "w") as f:
        json.dump(data, f)
        f.flush()
        if hasattr(os, "sync"):
            os.sync()

    try:
        os.remove(bak)
    except OSError:
        pass

    try:
        os.rename(filename, bak)
    except OSError:
        pass

    try:
        os.remove(filename)
    except OSError:
        pass

    os.rename(tmp, filename)

# def write_file_as_json(filename: str, data: dict) -> None:
#     with open(filename, 'w') as f:
#         json.dump(data, f)
