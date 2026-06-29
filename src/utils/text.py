def repair_mojibake(value: str) -> str:
    if not value:
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired != value else value


def text_variants(value: str):
    if not value:
        return
    yield value
    repaired = repair_mojibake(value)
    if repaired != value:
        yield repaired
