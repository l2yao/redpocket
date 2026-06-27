"""Detect red pockets inside a WeChat conversation."""

import logging
import time
from typing import List, Tuple

from .text_utils import text_variants
from .ui_scan import find_by_auto_id, iter_descendants_bounded

logger = logging.getLogger(__name__)

# WeChat red-packet messages usually expose accessibility text in English or
# Chinese. Keep the phrases broad because WeChat's Windows UI varies by build.
RED_PACKET_HINTS = [
    "red packet",
    "wechat red packet",
    "receive red packet",
    "view red packet",
    "红包",
    "微信红包",
    "查看红包",
    "领取红包",
    "领红包",
]


COLLECTED_MARKERS = [
    "opened",
    "received",
    "expired",
    "taken",
    "已领取",
    "已被领完",
    "已打开",
    "已拆开",
    "已过期",
    "领取完",
    "领取了",
    "你领取了",
]

CHAT_MESSAGE_LIST_IDS = ["chat_message_page", "chat_message_list"]
SCAN_TIMEOUT = 6.0


def _iter_text_values(elem):
    """Yield text-like values that may expose a red-packet hint."""
    getters = [
        lambda e: e.window_text(),
        lambda e: e.automation_id(),
    ]
    for getter in getters:
        try:
            value = getter(elem) or ""
        except Exception:
            continue
        for variant in text_variants(str(value)):
            yield variant

    try:
        legacy = elem.legacy_properties() or {}
    except Exception:
        return

    for key in ("Value", "Name", "Description", "Help"):
        value = legacy.get(key, "") or ""
        for variant in text_variants(str(value)):
            yield variant


def _contains_any(value: str, needles) -> bool:
    lower = value.lower()
    return any(needle.lower() in lower for needle in needles)


def _looks_like_red_packet(elem) -> bool:
    """Return True if the element looks like a red packet (collected or not).

    We skip the ``COLLECTED_MARKERS`` check because WeChat for Windows does not
    update the bubble's accessible text when a red packet is collected — it only
    adds a visual overlay.  Instead we treat every bubble containing a
    red-packet hint as a candidate; the collector will click it and detect
    whether a dialog appears.
    """
    values = list(_iter_text_values(elem))
    if not values:
        return False
    has_hint = any(_contains_any(value, RED_PACKET_HINTS) for value in values)
    if not has_hint:
        return False
    # System notifications have empty automation_id and are not clickable
    try:
        aid = elem.automation_id() or ""
        if not aid:
            return False
    except Exception:
        pass
    return True


def _find_red_packet_element(elem, deadline: float):
    """Return the most specific child that looks like an unopened red packet."""
    if time.time() > deadline:
        return None

    try:
        children = list(elem.children())
    except Exception:
        children = []

    for child in children:
        match = _find_red_packet_element(child, deadline)
        if match is not None:
            return match

    if _looks_like_red_packet(elem):
        return elem
    return None


def _find_message_list(window, timeout=SCAN_TIMEOUT):
    """Locate the chat message list pane by polling known automation IDs."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for aid in CHAT_MESSAGE_LIST_IDS:
            result = find_by_auto_id(window, aid, timeout=1.0)
            if result is not None:
                return result
        time.sleep(0.3)
    return None


def _elem_key(elem):
    """Return a key for deduplication — bounding box prefers, falls back to id()."""
    try:
        r = elem.rectangle()
        return ("rect", r.left, r.top, r.right, r.bottom)
    except Exception:
        return ("id", id(elem))


def find_red_packets_in_current_chat(window) -> List:
    """Scan the message pane of the current chat for red-packet bubbles."""
    packets = []
    seen_keys = set()
    deadline = time.time() + SCAN_TIMEOUT

    message_list = _find_message_list(window, timeout=max(1.0, deadline - time.time()))
    if message_list is None:
        logger.warning("Could not find chat_message_list; skipping red-packet scan.")
        return packets

    try:
        for elem in iter_descendants_bounded(message_list, deadline=deadline):
            try:
                aid_values = list(text_variants(elem.automation_id() or ""))
            except Exception:
                aid_values = []
            text_values = list(_iter_text_values(elem))
            looks_relevant = any(
                _contains_any(value, RED_PACKET_HINTS) for value in text_values
            ) or any(
                _contains_any(value, ["chat_bubble_item_view", "message"])
                for value in aid_values
            )
            if not looks_relevant:
                continue
            match = _find_red_packet_element(elem, deadline)
            if match is not None:
                k = _elem_key(match)
                if k not in seen_keys:
                    packets.append(match)
                    seen_keys.add(k)
    except Exception:
        logger.exception("Error scanning for red packets.")
    return packets


def find_red_packets_in_chat_list(window, chat_list=None) -> List[Tuple[str, object]]:
    """Scan the left-side chat list for conversations showing a red-pocket badge."""
    results = []
    try:
        if chat_list is None:
            chat_list = find_by_auto_id(window, "session_list", timeout=SCAN_TIMEOUT)
        if chat_list is None:
            return results

        for item in chat_list.children():
            try:
                text = item.window_text() or ""
            except Exception:
                text = ""
            if not any(
                _contains_any(value, ["[WeChat Red Packet]", "红包"])
                for value in text_variants(text)
            ):
                continue
            try:
                aid = item.automation_id() or ""
            except Exception:
                aid = ""
            name = aid.replace("session_item_", "") if aid.startswith("session_item_") else text.split("\n")[0].strip()
            results.append((name, item))
    except Exception:
        logger.exception("Error scanning chat list for red-pocket badges.")
    return results
