from __future__ import annotations

import logging
import time
from typing import List, Optional

import pyautogui

from ..client import WeChatClient
from ..ui.scanner import (
    click_center,
    find_by_auto_id,
    find_by_text,
    get_bounds,
    iter_descendants_bounded,
)

logger = logging.getLogger(__name__)

RED_PACKET_HINTS = [
    "red packet", "wechat red packet", "receive red packet", "view red packet",
    "红包", "微信红包", "查看红包", "领取红包", "领红包",
]

COLLECTED_MARKERS = [
    "opened", "received", "expired", "taken",
    "已领取", "已被领完", "已打开", "已拆开", "已过期", "领取完", "领取了", "你领取了",
]

CHAT_MESSAGE_LIST_IDS = ["chat_message_page", "chat_message_list"]

RED_PACKET_BUTTON_TEXTS = {"open", "打开", "领取", "领取红包", "领红包", "开"}

DIALOG_DISMISS_TEXTS = {"ok", "done", "确定", "完成", "关闭", "close"}


def _elem_key(elem):
    try:
        r = elem.BoundingRectangle
        return ("rect", r.left, r.top, r.right, r.bottom)
    except Exception:
        return ("id", id(elem))


def _looks_like_red_packet(elem) -> bool:
    try:
        text = (elem.Name or "").lower()
        aid = elem.AutomationId or ""
        if any(hint in text for hint in RED_PACKET_HINTS):
            return bool(aid)
    except Exception:
        pass
    return False


def _find_message_list(window, timeout: float = 6.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for aid in CHAT_MESSAGE_LIST_IDS:
            result = find_by_auto_id(window, aid, timeout=1.0)
            if result is not None:
                return result
        time.sleep(0.3)
    return None


def _find_red_packet_element(elem, deadline: float):
    if time.time() > deadline:
        return None
    try:
        children = elem.GetChildren()
    except Exception:
        children = []
    for child in children:
        match = _find_red_packet_element(child, deadline)
        if match is not None:
            return match
    if _looks_like_red_packet(elem):
        return elem
    return None


def find_red_packets_in_chat(window) -> List:
    packets = []
    seen_keys = set()
    deadline = time.time() + 6.0
    message_list = _find_message_list(window, timeout=min(1.0, deadline - time.time()))
    if message_list is None:
        logger.warning("Message list not found")
        return packets
    try:
        for elem in iter_descendants_bounded(message_list, deadline=deadline):
            try:
                text = (elem.Name or "").lower()
            except Exception:
                text = ""
            if not any(hint in text for hint in RED_PACKET_HINTS):
                continue
            match = _find_red_packet_element(elem, deadline)
            if match is not None:
                k = _elem_key(match)
                if k not in seen_keys:
                    packets.append(match)
                    seen_keys.add(k)
    except Exception:
        logger.exception("Error scanning for red packets")
    return packets


class RedPacketCollector:
    def __init__(self, client: WeChatClient, max_per_run: int = 10):
        self.client = client
        self.max_per_run = max_per_run
        self.collected = 0
        self._current_chat: Optional[str] = None
        self._tried_keys: set = set()

    @property
    def reached_cap(self) -> bool:
        return self.collected >= self.max_per_run

    def _wait_for_message_list(self, timeout: float = 8.0) -> bool:
        return _find_message_list(self.client.window, timeout=timeout) is not None

    def _scroll_up_in_chat(self):
        self.client.scroll_chat_up()

    def _wait_for_dialog(self, timeout: float = 3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Check for red packet dialog by looking for the Open button
            # In WeChat 4.0+, this is an overlay within the main window
            w = self.client.window
            if w is not None:
                try:
                    for elem in iter_descendants_bounded(w, max_nodes=500):
                        try:
                            txt = (elem.Name or "").lower()
                            if txt in RED_PACKET_BUTTON_TEXTS:
                                return elem
                        except Exception:
                            continue
                except Exception:
                    pass
            time.sleep(0.3)
        return None

    def _click_open_button(self, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            w = self.client.window
            if w is not None:
                try:
                    for elem in iter_descendants_bounded(w, max_nodes=500):
                        try:
                            txt = (elem.Name or "").lower()
                            if txt in RED_PACKET_BUTTON_TEXTS:
                                if click_center(elem):
                                    time.sleep(0.5)
                                    return True
                        except Exception:
                            continue
                except Exception:
                    pass
            time.sleep(0.3)
        return False

    def _close_overlay(self):
        try:
            pyautogui.press("escape")
            time.sleep(0.3)
        except Exception:
            pass

    def collect_from_chat(self, chat_name: str) -> int:
        if chat_name != self._current_chat:
            if not self.client.select_chat(chat_name):
                logger.warning("Failed to open chat '%s'", chat_name)
                return 0
            self._current_chat = chat_name
            time.sleep(1.5)
        if not self._wait_for_message_list(timeout=5.0):
            return 0
        packets = find_red_packets_in_chat(self.client.window)
        logger.info("Found %d red packet(s) in '%s'", len(packets), chat_name)
        if not packets:
            self._scroll_up_in_chat()
            time.sleep(1.5)
            packets = find_red_packets_in_chat(self.client.window)
            logger.info("After scroll: %d red packet(s) in '%s'", len(packets), chat_name)
        collected_here = 0
        for packet in packets:
            if self.collected >= self.max_per_run:
                break
            try:
                r = packet.BoundingRectangle
                key = (r.left, r.top, r.right, r.bottom)
            except Exception:
                key = None
            if key is not None and key in self._tried_keys:
                continue
            if click_center(packet):
                time.sleep(1)
                if self._click_open_button(timeout=2.0):
                    self._tried_keys.clear()
                    self.collected += 1
                    collected_here += 1
                    logger.info("Collected red packet #%d in '%s'", self.collected, chat_name)
                else:
                    if key is not None:
                        self._tried_keys.add(key)
                self._close_overlay()
                time.sleep(0.5)
        self._close_overlay()
        return collected_here
