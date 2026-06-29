from __future__ import annotations

import logging
import time
from typing import Iterator, Optional

import uiautomation as uia

logger = logging.getLogger(__name__)

DEFAULT_SCAN_TIMEOUT = 8.0


def iter_descendants_bounded(
    root,
    deadline: Optional[float] = None,
    max_nodes: int = 2000,
) -> Iterator:
    if root is None:
        return
    count = 0
    try:
        for elem in root.GetChildren():
            stack = [elem]
            while stack and (deadline is None or time.time() <= deadline) and count < max_nodes:
                current = stack.pop()
                count += 1
                yield current
                try:
                    children = current.GetChildren()
                    # Reverse so UIA traversal order matches original
                    stack.extend(reversed(children))
                except Exception:
                    continue
    except Exception as exc:
        logger.debug("UI scan stopped: %s", exc)


def find_by_auto_id(
    root,
    auto_id: str,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    max_nodes: int = 2000,
):
    if root is None or not auto_id:
        return None
    deadline = time.time() + timeout
    for elem in iter_descendants_bounded(root, deadline=deadline, max_nodes=max_nodes):
        try:
            if (elem.AutomationId or "") == auto_id:
                return elem
        except Exception:
            continue
    return None


def find_by_text(
    root,
    text: str,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    max_nodes: int = 2000,
    case_sensitive: bool = False,
):
    if root is None or not text:
        return None
    deadline = time.time() + timeout
    target = text if case_sensitive else text.lower()
    for elem in iter_descendants_bounded(root, deadline=deadline, max_nodes=max_nodes):
        try:
            name = (elem.Name or "")
            if not case_sensitive:
                name = name.lower()
            if target in name:
                return elem
        except Exception:
            continue
    return None


def find_control(root, conditions: dict, timeout: float = DEFAULT_SCAN_TIMEOUT) -> Optional:
    root_c = root
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if isinstance(root_c, uia.WindowControl):
                ctrl = root_c.FindControl(condition_func=lambda c: all(
                    getattr(c, k, None) == v for k, v in conditions.items()
                ), searchDepth=10)
            else:
                ctrl = root_c.FindControl(condition_func=lambda c: all(
                    getattr(c, k, None) == v for k, v in conditions.items()
                ), searchDepth=10)
            if ctrl:
                return ctrl
        except Exception:
            pass
        time.sleep(0.3)
    return None


def get_bounds(elem):
    try:
        rect = elem.BoundingRectangle
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return 0, 0, 0, 0


def click_center(elem):
    import pyautogui
    left, top, right, bottom = get_bounds(elem)
    if right - left <= 0 or bottom - top <= 0:
        return False
    cx = (left + right) // 2
    cy = (top + bottom) // 2
    pyautogui.moveTo(cx, cy, duration=0.1)
    time.sleep(0.05)
    pyautogui.click()
    return True
