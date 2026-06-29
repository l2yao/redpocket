from __future__ import annotations

import logging
import time
from typing import Iterator, Optional

import pyautogui
import uiautomation as uia

from .ui.scanner import (
    click_center,
    find_by_auto_id,
    find_by_text,
    get_bounds,
    iter_descendants_bounded,
)

logger = logging.getLogger(__name__)


class WeChatClient:
    def __init__(self, title: str = "WeChat"):
        self._configured_title = title
        self._window: Optional[uia.WindowControl] = None
        self._connected = False
        self._current_chat: Optional[str] = None

    @property
    def window(self):
        return self._window

    @property
    def is_new_ui(self) -> bool:
        if self._window is None:
            return False
        try:
            return "mmui" in (self._window.ClassName or "")
        except Exception:
            return True

    def connect(self, timeout: int = 15) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                root = uia.GetRootControl()
                for w in root.GetChildren():
                    name = w.Name or ""
                    cls = w.ClassName or ""
                    if self._configured_title.lower() in name.lower():
                        if "mmui" in cls or "WeChat" in cls or "Weixin" in cls or "WeChatAppEx" in cls:
                            self._window = uia.WindowControl(Name=name, ClassName=cls)
                            self._window.SetTopmost(True)
                            self._window.SetFocus()
                            self._connected = True
                            logger.info("Connected to WeChat: %s (class=%s)", name, cls)
                            return True
                for w in root.GetChildren():
                    name = w.Name or ""
                    if "微信" in name or "WeChat" in name or "Weixin" in name:
                        cls = w.ClassName or ""
                        self._window = uia.WindowControl(Name=name, ClassName=cls)
                        self._window.SetTopmost(True)
                        self._window.SetFocus()
                        self._connected = True
                        logger.info("Connected to WeChat: %s (class=%s)", name, cls)
                        return True
            except Exception as exc:
                logger.debug("Connect attempt failed: %s", exc)
            time.sleep(1)
        logger.error("Could not find WeChat window (title=%s)", self._configured_title)
        return False

    def ensure_connected(self) -> bool:
        if self._connected and self._window is not None:
            try:
                _ = self._window.Name
                return True
            except Exception:
                self._connected = False
                self._window = None
        return self.connect()

    def focus(self):
        if self._window:
            try:
                self._window.SetTopmost(True)
                self._window.SetFocus()
            except Exception:
                pass

    def get_chat_list(self):
        return find_by_auto_id(self._window, "session_list", timeout=4.0)

    def list_chat_items(self) -> Iterator[tuple[str, object]]:
        chat_list = self.get_chat_list()
        if chat_list is None:
            return
        seen = set()
        for _ in range(30):
            found_any = False
            for item in iter_descendants_bounded(chat_list, max_nodes=400):
                try:
                    aid = item.AutomationId or ""
                    if not aid.startswith("session_item_"):
                        continue
                    name = aid.replace("session_item_", "")
                    if name and name not in seen:
                        seen.add(name)
                        yield name, item
                        found_any = True
                except Exception:
                    continue
            if not found_any:
                break
            try:
                chat_list.SetFocus()
                pyautogui.scroll(-3)
            except Exception:
                break
            time.sleep(0.3)

    def _find_chat_item(self, name: str):
        item = find_by_auto_id(self._window, f"session_item_{name}", timeout=4.0)
        if item is not None:
            return item
        chat_list = self.get_chat_list()
        if chat_list is None:
            return None
        normalized = self._normalize(name)
        for item in iter_descendants_bounded(chat_list, max_nodes=400):
            try:
                aid = item.AutomationId or ""
                if aid.startswith("session_item_"):
                    candidate = aid.replace("session_item_", "")
                    if self._normalize(candidate) == normalized:
                        return item
            except Exception:
                continue
        return None

    def _normalize(self, name: str) -> str:
        if not name:
            return ""
        return "".join(ch.lower() for ch in name if ch.isalnum())

    def _keyboard_select_chat(self, name: str) -> bool:
        self.focus()
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        pyautogui.write(name, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(1.5)
        pyautogui.press("escape")
        time.sleep(0.3)
        return True

    def _keyboard_send_message(self, text: str) -> bool:
        self.focus()
        time.sleep(0.3)
        pyautogui.write(text, interval=0.02)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.5)
        return True

    def select_chat(self, name: str) -> bool:
        if not self.ensure_connected():
            return False
        self.focus()
        time.sleep(0.2)
        item = self._find_chat_item(name)
        if item is not None:
            click_center(item)
            time.sleep(0.8)
            self._current_chat = name
            return True
        if self.is_new_ui:
            logger.info("Using keyboard search to find '%s'", name)
            return self._keyboard_select_chat(name)
        logger.warning("Could not find chat '%s'", name)
        return False

    def send_message(self, text: str, chat_name: Optional[str] = None) -> bool:
        if not self.ensure_connected():
            return False
        if chat_name is not None and chat_name != self._current_chat:
            if not self.select_chat(chat_name):
                return False
        input_field = find_by_auto_id(self._window, "chat_input_field", timeout=3.0)
        if input_field is not None:
            click_center(input_field)
            time.sleep(0.3)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("delete")
            time.sleep(0.1)
            pyautogui.write(text, interval=0.02)
            time.sleep(0.2)
            send_btn = find_by_text(self._window, "send", timeout=2.0)
            if send_btn is not None:
                click_center(send_btn)
            else:
                pyautogui.press("enter")
            time.sleep(0.5)
            logger.info("Message sent to '%s' via input field", chat_name or self._current_chat)
            return True
        logger.info("Using keyboard send to '%s'", chat_name or self._current_chat)
        return self._keyboard_send_message(text)

    def scroll_chat_up(self):
        msg_list = find_by_auto_id(self._window, "chat_message_page", timeout=3.0)
        if msg_list is None:
            msg_list = find_by_auto_id(self._window, "chat_message_list", timeout=3.0)
        if msg_list is not None:
            left, top, right, bottom = get_bounds(msg_list)
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            for _ in range(3):
                pyautogui.scroll(3, cx, cy)
                time.sleep(0.3)
            return True
        return False

    def close_red_packet_dialog(self):
        import uiautomation as uia
        from pywinauto import Desktop as _Desktop

        try:
            deadline = time.time() + 3
            while time.time() < deadline:
                root = uia.GetRootControl()
                found = False
                for w in root.GetChildren():
                    try:
                        aid = w.AutomationId or ""
                        cls = w.ClassName or ""
                        if "PayRedEnvelopDetailWindow" in aid + cls:
                            pyautogui.press("escape")
                            time.sleep(0.5)
                            found = True
                            break
                    except Exception:
                        continue
                if found:
                    continue
                try:
                    for elem in self._window.GetChildren() if self._window else []:
                        try:
                            txt = (elem.Name or "").lower()
                            if txt in ("ok", "done", "确定", "完成", "关闭", "close"):
                                click_center(elem)
                                time.sleep(0.3)
                                found = True
                        except Exception:
                            continue
                except Exception:
                    pass
                if not found:
                    break
                time.sleep(0.3)
        except Exception:
            logger.debug("Error closing red packet dialog", exc_info=True)
