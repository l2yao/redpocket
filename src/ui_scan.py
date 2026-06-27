"""Bounded UI tree traversal helpers for WeChat automation."""

from __future__ import annotations

import logging
import time
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

DEFAULT_SCAN_TIMEOUT = 8.0


def iter_descendants_bounded(
    root,
    deadline: Optional[float] = None,
    max_nodes: int = 2000,
) -> Iterator:
    """Walk UI descendants with optional time and node limits.

    WeChat exposes most controls only through ``descendants()``, not a shallow
    ``children()`` chain, so we iterate descendants and stop early when possible.
    """
    if root is None:
        return

    count = 0
    try:
        for elem in root.descendants():
            if deadline is not None and time.time() > deadline:
                logger.debug("UI scan stopped: deadline reached.")
                return
            if count >= max_nodes:
                logger.debug("UI scan stopped: node limit reached.")
                return
            count += 1
            yield elem
    except Exception as exc:
        logger.debug("UI scan stopped: %s", exc)


def find_by_auto_id(
    root,
    auto_id: str,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    max_nodes: int = 2000,
):
    """Find the first element with the given automation id within a time budget."""
    if root is None or not auto_id:
        return None

    deadline = time.time() + timeout
    for elem in iter_descendants_bounded(root, deadline=deadline, max_nodes=max_nodes):
        try:
            if (elem.automation_id() or "") == auto_id:
                return elem
        except Exception:
            continue
    return None
