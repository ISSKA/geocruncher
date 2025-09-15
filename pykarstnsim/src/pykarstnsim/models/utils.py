def parse_int_strict(s: str) -> int:
    f = float(s)
    if not f.is_integer():
        raise ValueError(f"String does not represent an integer: {s}")
    return int(f)
