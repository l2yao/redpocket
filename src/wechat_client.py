"""Helpers to locate and interact with the WeChat for Windows client."""

import os
import subprocess
import time
import logging
from typing import List, Optional

from pywinauto import Application, Desktop
from pywinauto.findwindows import ElementNotFoundError
import pyautogui

from .ui_scan import find_by_auto_id, iter_descendants_bounded

logger = logging.getLogger(__name__)

# Common WeChat window titles across different language versions
COMMON_WECHAT_TITLES = ["WeChat", "Weixin", "微信"]


class WeChatClient:
    """Wraps pywinauto to find the WeChat window and its UI elements."""

    def __init__(self, title: str = "WeChat"):
        self._configured_title = title
        self._resolved_title: Optional[str] = None
        self.app: Optional[Application] = None
        self.window = None
        self._session_list = None
        self._current_chat: Optional[str] = None

    @property
    def _candidate_titles(self) -> List[str]:
        """Return the list of titles to try, with the configured one first."""
        titles = [self._configured_title]
        for t in COMMON_WECHAT_TITLES:
            if t.lower() not in [x.lower() for x in titles]:
                titles.append(t)
        return titles

    def _find_main_window(self) -> Optional[object]:
        """Find the main WeChat window by scanning all windows for any common title.

        Prefers ``mmui::MainWindow`` over ``mmui::PayRedEnvelopDetailWindow``
        when both are open (same title "WeChat").
        """
        best = None
        try:
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    title = w.window_text() or ""
                    if not any(candidate.lower() in title.lower() for candidate in self._candidate_titles):
                        continue
                    cls = w.element_info.class_name or ""
                    if "PayRedEnvelopDetailWindow" in cls:
                        # Remember dialog as fallback, but prefer main window
                        if best is None:
                            best = w
                            best._is_dialog = True
                        continue
                    self._resolved_title = next(c for c in self._candidate_titles if c.lower() in title.lower())
                    return w
                except Exception:
                    continue
        except Exception:
            pass
        return best

    def _resolve_main_window(self):
        """Return the main WeChat UIA wrapper, skipping red-packet dialogs."""
        if self.app is None:
            return None
        title = self._resolved_title or self._configured_title
        try:
            wrapper = self.app.window(title_re=f".*{title}.*").wrapper_object()
            aid = ""
            cls = ""
            try:
                aid = wrapper.automation_id() or ""
                cls = wrapper.element_info.class_name or ""
            except Exception:
                pass
            # Skip the detail-dialog window (same title but different class)
            if "PayRedEnvelopDetailWindow" in aid + cls:
                return None
            return wrapper
        except Exception:
            return None

    def connect(self, timeout: int = 15) -> bool:
        """Connect to the running WeChat process by scanning for any WeChat window."""
        # First, find the main window by scanning all desktop windows
        main_window = self._find_main_window()
        if main_window is not None:
            try:
                process_id = main_window.process_id()
                if process_id:
                    self.app = Application(backend="uia").connect(process=process_id)
                    wrapper = self._resolve_main_window()
                    if wrapper is not None:
                        self.window = wrapper
                        self._invalidate_session_list()
                        self.window.set_focus()
                        logger.info(
                            "Connected to WeChat window: %s",
                            self.window.window_text(),
                        )
                        return True
            except Exception:
                pass

        # Fallback: try title-based connection with each candidate
        deadline = time.time() + timeout
        while time.time() < deadline:
            for title in self._candidate_titles:
                try:
                    if self.app is None:
                        self.app = Application(backend="uia").connect(
                            title_re=f".*{title}.*", timeout=3
                        )
                    self._resolved_title = title
                    wrapper = self._resolve_main_window()
                    if wrapper is not None:
                        self.window = wrapper
                        self._invalidate_session_list()
                        self.window.set_focus()
                        logger.info(
                            "Connected to WeChat window: %s (title=%r)",
                            self.window.window_text(),
                            title,
                        )
                        return True
                except ElementNotFoundError:
                    self.app = None
                    continue
                except Exception as e:
                    logger.debug("Connect error with title %r: %s; retrying.", title, e)
                    self.app = None
                    continue
            time.sleep(1)
        logger.error("Could not find a WeChat window. Tried titles: %s", self._candidate_titles)
        return False

    def ensure_connected(self) -> bool:
        """Reconnect if needed. Tolerates transient failures by retrying."""
        if self.app is None or self.window is None:
            return self.connect()
        try:
            _ = self.window.window_text()
            return True
        except Exception:
            pass
        logger.debug("WeChat window lost; attempting reconnect.")
        self.app = None
        self.window = None
        self._session_list = None
        return self.connect()

    def _invalidate_session_list(self):
        self._session_list = None

    def _find_by_auto_id(self, auto_id: str, control_type: str = ""):
        """Search descendants for an element by automation id within a time budget."""
        if self.window is None:
            return None
        return find_by_auto_id(self.window, auto_id, timeout=10.0, max_nodes=500)

    def _normalize_chat_name(self, name: str) -> str:
        """Normalize chat names for robust matching across spacing and punctuation."""
        if not name:
            return ""
        return "".join(ch.lower() for ch in name if ch.isalnum())

    def _get_session_list(self):
        """Return the cached session list, refreshing if needed."""
        if self._session_list is not None:
            try:
                self._session_list.wrapper_object()
                return self._session_list
            except Exception:
                self._session_list = None
        self._session_list = self._find_by_auto_id("session_list")
        return self._session_list

    def _find_chat_item(self, name: str):
        """Find a chat item by automation id or by visible text in the session list.

        If the item is not visible (scrolled out of view), scroll the chat list
        page by page and retry until it is found.
        """
        item = find_by_auto_id(self.window, f"session_item_{name}", timeout=4.0)
        if item is not None:
            return item

        item = self._find_chat_item_in_session_list(name)
        if item is not None:
            return item

        # Item not in the visible portion — scroll down to find it
        chat_list = self._get_session_list()
        if chat_list is None:
            return None

        logger.info("Scrolling chat list to find '%s'...", name)
        # Try scrolling both directions to cover pinned (top) and old (bottom)
        for direction in ("down", "up"):
            for _ in range(50):
                try:
                    chat_list.scroll(direction, "page")
                except Exception:
                    break
                time.sleep(0.3)
                item = self._find_chat_item_in_session_list(name)
                if item is not None:
                    logger.debug("Found '%s' after scrolling %s.", name, direction)
                    return item

        logger.warning("Could not find chat item '%s' after scrolling.", name)
        return None

    def _find_chat_item_in_session_list(self, name: str):
        """Search for a chat item within the visible portion of the session list."""
        chat_list = self._get_session_list()
        if chat_list is None:
            return None

        target = self._normalize_chat_name(name)
        for item in iter_descendants_bounded(chat_list, max_nodes=400):
            try:
                aid = item.automation_id() or ""
                text = (item.window_text() or "").strip()
                if aid == f"session_item_{name}":
                    return item
                candidates = []
                if aid.startswith("session_item_"):
                    candidates.append(aid.replace("session_item_", ""))
                if text:
                    candidates.append(text.split("\n", 1)[0])
                if target and any(
                    target in self._normalize_chat_name(candidate)
                    for candidate in candidates
                ):
                    return item
            except Exception:
                continue
        return None

    def _is_red_packet_dialog_open(self) -> bool:
        """Return True if the red packet detail dialog is the active window.

        The dialog replaces the main WeChat window.  We detect it by
        checking whether the window's ``automation_id`` contains
        ``PayRedEnvelopDetailWindow``.
        """
        try:
            aid = self.window.automation_id() or ""
            return "PayRedEnvelopDetailWindow" in aid
        except Exception:
            return False

    def _is_main_window(self) -> bool:
        """Return True if the main WeChat window is active (has session_list)."""
        return self._get_session_list() is not None

    def close_red_packet_dialog(self):
        """Dismiss any red packet dialogs if open.

        Handles both a separate ``mmui::PayRedEnvelopDetailWindow`` (focused
        Escape) and an overlay within the main window (search for an OK/Done
        button and click it).  Does *not* invalidate the main window reference.
        """
        import pyautogui
        from pywinauto import Desktop as _Desktop

        def _is_dismiss_button(elem):
            try:
                txt = (elem.window_text() or "").lower()
                ct = elem.element_info.control_type or ""
                return ct == "Button" and txt in ("ok", "done", "确定", "完成", "关闭", "close", "×")
            except Exception:
                return False

        try:
            # 1. Check all top-level windows for a separate dialog
            try:
                desktop = _Desktop(backend="uia")
                for w in desktop.windows():
                    try:
                        aid = w.automation_id() or ""
                        cls = w.element_info.class_name or ""
                        if "PayRedEnvelopDetailWindow" in aid + cls:
                            logger.info("Red packet detail window found; closing.")
                            w.set_focus()
                            time.sleep(0.3)
                            try:
                                w.close()
                            except Exception:
                                pass
                            time.sleep(0.5)
                            return
                    except Exception:
                        continue
            except Exception:
                pass

            # 2. Within the main window, look for a dismiss button (receipt overlay)
            if self.window is not None:
                try:
                    for e in self.window.descendants():
                        if _is_dismiss_button(e):
                            logger.info("Receipt overlay dismiss button found; clicking it.")
                            try:
                                rect = e.rectangle()
                                cx = (rect.left + rect.right) // 2
                                cy = (rect.top + rect.bottom) // 2
                                pyautogui.moveTo(cx, cy, duration=0.05)
                                time.sleep(0.05)
                                pyautogui.click()
                                time.sleep(0.5)
                            except Exception:
                                pass
                            return
                except Exception:
                    pass

        except Exception:
            logger.debug("No red packet dialog found to close.")

    def get_chat_list(self):
        """Return the session list control (the left-side conversation list)."""
        self.ensure_connected()
        elem = self._get_session_list()
        if elem is None:
            logger.warning("Could not locate the session_list control.")
        return elem

    def list_chat_items(self):
        """Yield (name, wrapper) for each conversation in the chat list.

        Scrolls through the full list so off-screen items are included.
        """
        chat_list = self.get_chat_list()
        if chat_list is None:
            return
        seen = set()
        for _ in range(30):
            found_any = False
            for item in iter_descendants_bounded(chat_list, max_nodes=400):
                try:
                    aid = item.automation_id() or ""
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
                chat_list.scroll("down", "page")
            except Exception:
                break
            time.sleep(0.3)

    def _click_wrapper_center(self, wrapper) -> None:
        """Click the center of a wrapper using a real mouse event."""
        try:
            rect = wrapper.rectangle()
            left = rect.left() if callable(getattr(rect, "left", None)) else getattr(rect, "left", 0)
            top = rect.top() if callable(getattr(rect, "top", None)) else getattr(rect, "top", 0)
            right = rect.right() if callable(getattr(rect, "right", None)) else getattr(rect, "right", 0)
            bottom = rect.bottom() if callable(getattr(rect, "bottom", None)) else getattr(rect, "bottom", 0)
            x = (left + right) // 2
            y = (top + bottom) // 2
            pyautogui.click(x, y)
        except Exception:
            logger.debug("Could not click wrapper center; falling back to click_input.")
            wrapper.click_input()

    def select_chat(self, name: str) -> bool:
        """Click a conversation by name to open it.

        WeChat tags each session item with ``auto_id='session_item_<name>'``.
        When that ID is missing, fall back to visible text matching.

        IMPORTANT: clicking an already-open chat CLOSES it.  The caller must
        avoid re-selecting the same chat.  Use :meth:`chat_is_open` to check.
        """
        if not self.ensure_connected():
            logger.warning("Cannot select chat '%s' because WeChat is not connected.", name)
            return False
        if self.window is None:
            logger.warning("Cannot select chat '%s' because the WeChat window is unavailable.", name)
            return False
        item = self._find_chat_item(name)
        if item is None:
            logger.warning("Could not find chat item for '%s'.", name)
            return False
        self.window.set_focus()
        time.sleep(0.2)
        self._click_wrapper_center(item)
        time.sleep(0.5)
        return True

    def chat_is_open(self) -> bool:
        """Return True if a chat view (message list) is currently visible."""
        from .redpacket_finder import _find_message_list
        return _find_message_list(self.window, timeout=1.0) is not None

    def get_current_chat_name(self) -> Optional[str]:
        """Return the title of the currently open conversation."""
        self.ensure_connected()
        try:
            label = find_by_auto_id(self.window, "current_chat_name_label", timeout=2.0)
            if label is not None:
                return label.window_text() or None
        except Exception:
            pass
        try:
            pane = self.window.child_control(control_type="Pane", found_index=0)
            return pane.window_text()
        except Exception:
            return None

    def send_message(self, text: str, chat_name: str = None) -> bool:
        """Send *text* to *chat_name* (or the current chat).

        Returns True on success.
        """
        if not self.ensure_connected():
            return False

        self.close_red_packet_dialog()

        # Switch chat if requested — never re-select an already-open chat
        if chat_name is not None and chat_name != self._current_chat:
            current = self.get_current_chat_name()
            need_switch = True
            if current is not None and current == chat_name:
                need_switch = False
            elif current is None and self.chat_is_open():
                need_switch = False
            if need_switch:
                if not self.select_chat(chat_name):
                    logger.warning("Failed to open chat '%s'.", chat_name)
                    return False
            self._current_chat = chat_name
            time.sleep(1.5)

        # Wait for the input field to appear (retry loop)
        found = None
        for _ in range(10):
            found = find_by_auto_id(self.window, "chat_input_field", timeout=2.0)
            if found is not None:
                break
            time.sleep(0.5)
        if found is None:
            logger.warning("Could not find chat input field.")
            return False

        # Click the input field to focus it
        try:
            rect = found.rectangle()
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            pyautogui.moveTo(cx, cy, duration=0.1)
            time.sleep(0.05)
            pyautogui.click()
            time.sleep(0.3)
        except Exception:
            logger.warning("Could not click input field.")
            return False

        # Clear any existing text and type the message
        try:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("delete")
            time.sleep(0.1)
        except Exception:
            pass
        pyautogui.write(text, interval=0.02)
        time.sleep(0.2)

        # Find and click the Send button (XOutlineButton with text='send')
        try:
            for e in self.window.descendants():
                try:
                    txt = (e.window_text() or "").lower()
                    ct = e.element_info.control_type or ""
                    cls = e.element_info.class_name or ""
                    if ct == "Button" and txt == "send" and "OutlineButton" in cls:
                        rect = e.rectangle()
                        cx = (rect.left + rect.right) // 2
                        cy = (rect.top + rect.bottom) // 2
                        pyautogui.moveTo(cx, cy, duration=0.1)
                        time.sleep(0.05)
                        pyautogui.click()
                        time.sleep(0.5)
                        logger.info("Message sent to '%s'.", chat_name or self._current_chat)
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback: press Enter
        logger.debug("Send button not found; pressing Enter.")
        pyautogui.press("enter")
        time.sleep(0.5)
        return True

    def launch(self) -> bool:
        """Launch WeChat if it is not running.

        Tries common install paths.  Returns True if the process was
        started, False otherwise.
        """
        import subprocess

        # Common WeChat install locations
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tencent", "WeChat", "WeChat.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Tencent", "WeChat", "WeChat.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Tencent", "WeChat", "WeChat.exe"),
            os.path.join(os.environ.get("APPDATA", ""), "..", "Local", "Programs", "Tencent", "WeChat", "WeChat.exe"),
        ]
        # Also search the registry uninstall key for the install path
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat") as key:
                install_path, _ = winreg.QueryValueEx(key, "InstallLocation")
                candidate = os.path.join(install_path, "WeChat.exe")
                if candidate not in candidates:
                    candidates.insert(0, candidate)
        except Exception:
            pass

        for path in candidates:
            if path and os.path.isfile(path):
                logger.info("Launching WeChat from: %s", path)
                subprocess.Popen([path])
                return True

        logger.error("Could not find WeChat.exe in any known location.")
        return False

    def click_element_center(self, wrapper):
        """Click the center of a UI element wrapper."""
        rect = wrapper.rectangle()
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        pyautogui.click(cx, cy)
