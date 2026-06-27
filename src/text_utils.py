"""Text helpers for UI strings returned by WeChat automation."""

from __future__ import annotations


def repair_mojibake(value: str) -> str:
    """Repair common UTF-8-as-Latin-1 mojibake, returning the original on failure."""
    if not value:
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired != value else value


def text_variants(value: str):
    """Yield the original text and a repaired variant if it differs."""
    if not value:
        return
    yield value
    repaired = repair_mojibake(value)
    if repaired != value:
        yield repaired
