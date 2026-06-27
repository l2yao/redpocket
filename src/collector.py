"""Click into a conversation, open red pockets, and confirm the dialog."""

import logging
import time
from typing import Optional

import pyautogui

from .redpacket_finder import CHAT_MESSAGE_LIST_IDS, find_red_packets_in_current_chat
from .text_utils import text_variants
from .ui_scan import find_by_auto_id
from .wechat_client import WeChatClient

logger = logging.getLogger(__name__)


class RedPacketCollector:
    def __init__(self, client: WeChatClient, max_per_run: int = 10, confirm: bool = True):
        self.client = client
        self.max_per_run = max_per_run
        self.confirm = confirm
        self.collected = 0
        self._current_chat: Optional[str] = None
        self._tried_keys: set = set()

    def _get_rect_bounds(self, rect):
        """Return (left, top, right, bottom) for a rectangle-like object."""
        def read(name):
            value = getattr(rect, name, None)
            if callable(value):
                return value()
            return value

        return read("left"), read("top"), read("right"), read("bottom")

    def _click_element_center(self, elem):
        """Click the center of a UI element.

        Uses pyautogui with smooth mouse movement for the most realistic
        simulation — WeChat's custom Qt controls ignore synthetic events
        from ``invoke()`` and ``click_input()``.
        """
        rect = elem.rectangle()
        left, top, right, bottom = self._get_rect_bounds(rect)
        cx = (left + right) // 2
        cy = (top + bottom) // 2
        pyautogui.moveTo(cx, cy, duration=0.1)
        time.sleep(0.05)
        pyautogui.click()

    def _click_if_visible(self, elem) -> bool:
        """Click an element if it has a usable rectangle."""
        try:
            rect = elem.rectangle()
            left, top, right, bottom = self._get_rect_bounds(rect)
            if right - left <= 0 or bottom - top <= 0:
                return False
            self._click_element_center(elem)
            return True
        except Exception:
            return False

    def _wait_for_message_list(self, timeout: float = 8.0) -> bool:
        """Wait until the chat message list element is available in the UI tree."""
        from src.redpacket_finder import CHAT_MESSAGE_LIST_IDS, _find_message_list
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _find_message_list(self.client.window, timeout=1.0) is not None:
                return True
            time.sleep(0.5)
        return False

    def _scroll_up_in_chat(self):
        """Scroll up in the current chat to load older messages."""
        try:
            message_list = None
            for aid in CHAT_MESSAGE_LIST_IDS:
                message_list = find_by_auto_id(self.client.window, aid, timeout=3.0)
                if message_list is not None:
                    break
            if message_list is None:
                return
            rect = message_list.rectangle()
            left, top, right, bottom = self._get_rect_bounds(rect)
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            for _ in range(3):
                pyautogui.scroll(3, cx, cy)
                time.sleep(0.3)
            logger.debug("Scrolled up in chat to load older messages.")
        except Exception:
            logger.debug("Could not scroll in chat.")

    def collect_from_chat(self, chat_name: str) -> int:
        """Open a conversation and collect all visible red pockets.

        Returns the number of red packets collected from this chat.
        """
        # Only select the chat if it's not already open
        if chat_name != self._current_chat:
            # Check if the chat is already open (WeChat may remember the last chat)
            if not self.client.chat_is_open():
                if not self.client.select_chat(chat_name):
                    logger.warning("Failed to open chat '%s'.", chat_name)
                    return 0
            else:
                logger.debug("Chat '%s' is already open, skipping select_chat.", chat_name)
            self._current_chat = chat_name
            time.sleep(1.5)
        else:
            time.sleep(0.3)

        collected_here = 0

        # Ensure the message list is available before scanning
        if not self._wait_for_message_list(timeout=5.0):
            logger.warning("Chat message list not available after selecting '%s'.", chat_name)
            return 0

        scan_start = time.time()
        packets = find_red_packets_in_current_chat(self.client.window)
        logger.info(
            "Scanned '%s' in %.1fs — found %d red-packet candidate(s).",
            chat_name,
            time.time() - scan_start,
            len(packets),
        )

        # If no packets found, scroll up once and re-check (older messages only)
        if not packets:
            logger.info("No red packets visible in '%s', checking older messages...", chat_name)
            self._scroll_up_in_chat()
            time.sleep(1.5)
            self._wait_for_message_list(timeout=5.0)
            scan_start = time.time()
            packets = find_red_packets_in_current_chat(self.client.window)
            logger.info(
                "Rescan after scroll took %.1fs — found %d candidate(s).",
                time.time() - scan_start,
                len(packets),
            )

        # If still no packets, skip this group quickly
        if not packets:
            logger.info("No uncollected red packets in '%s', moving on.", chat_name)
            return 0

        for packet in packets:
            if self.collected >= self.max_per_run:
                logger.info("Per-run cap reached (%d).", self.max_per_run)
                return collected_here

            # Skip candidates we already tried in a previous polling cycle
            try:
                r = packet.rectangle()
                key = (r.left, r.top, r.right, r.bottom)
            except Exception:
                key = None
            if key is not None and key in self._tried_keys:
                continue

            try:
                rect = packet.rectangle()
                if rect.width() == 0 or rect.height() == 0:
                    continue
                self._click_element_center(packet)
                time.sleep(1)
                if self._confirm_and_close():
                    self._tried_keys.clear()
                    self.collected += 1
                    collected_here += 1
                    logger.info(
                        "Collected red packet #%d in '%s'.", self.collected, chat_name
                    )
                else:
                    if key is not None:
                        self._tried_keys.add(key)
                    self.client.close_red_packet_dialog()
            except Exception:
                logger.exception("Error clicking a red packet in '%s'.", chat_name)
                self.client.close_red_packet_dialog()

        # After collecting, make sure no dialog is left open
        self.client.close_red_packet_dialog()

        return collected_here

    def _find_dialog_window(self):
        """Search all top-level windows for the red packet dialog."""
        try:
            from pywinauto import Desktop as _Desktop
            desktop = _Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    aid = w.automation_id() or ""
                    text = (w.window_text() or "")
                    cls = w.element_info.class_name or ""
                except Exception:
                    continue
                # Match by automation ID
                if "PayRedEnvelopDetailWindow" in aid:
                    return w
                # Match by window class name (WeChat custom controls)
                if "PayRedEnvelopDetailWindow" in cls or "RedEnvelop" in cls:
                    return w
                # Match by title keywords (Chinese/English)
                if any(kw in text for kw in ("红包", "red packet", "Red Packet", "领取红包")):
                    return w
            return None
        except Exception:
            return None

    def _wait_for_any_dialog(self, timeout: float = 1.5):
        """Wait for the dialog to appear, returning the dialog window or None.

        The red-packet overlay appears as descendants of the main WeChat window
        (``mmui::MainWindow``), NOT as a separate top-level window.  It has:

        * a ``Text`` with text like ``"Red packet sent by ..."``
        * a ``Button`` with text ``"Open"`` / ``"打开"``

        We detect it by looking for the ``Button`` element directly, then
        return the main window as the dialog context for subsequent Open-button
        clicking.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Check for a separate top-level dialog window (older WeChat builds)
            dlg = self._find_dialog_window()
            if dlg is not None:
                return dlg

            # Check current window descendants for the overlay
            w = self.client.window
            if w is not None:
                try:
                    for elem in w.descendants():
                        try:
                            txt = (elem.window_text() or "").lower()
                            ct = elem.element_info.control_type or ""
                            cls = elem.element_info.class_name or ""
                            if ct == "Button" and txt in ("open", "打开", "领取", "领取红包", "领红包", "开"):
                                logger.debug("Found Open-button overlay (class=%s, text=%s)", cls, txt)
                                return w
                        except Exception:
                            continue
                except Exception:
                    pass

            time.sleep(0.3)
        return None

    def _get_automation_id(self, elem) -> str:
        """Best-effort retrieval of an automation id from a UI element."""
        try:
            value = elem.automation_id()
            if value:
                return str(value).strip()
        except Exception:
            pass
        return ""

    def _get_element_text(self, elem) -> str:
        """Best-effort text extraction from a UI element."""
        for getter in (lambda e: e.window_text(), self._get_automation_id):
            try:
                value = getter(elem) or ""
                if value:
                    return str(value).strip()
            except Exception:
                continue
        try:
            legacy = elem.legacy_properties() or {}
            value = legacy.get("Value", "") or ""
            if value:
                return str(value).strip()
        except Exception:
            pass
        return ""

    def _dump_window_controls(self, label: str = "window") -> None:
        """Log UI controls from the current window for interactive debugging."""
        try:
            if self.client.window is None:
                return
            logger.debug("%s controls:", label)
            for idx, elem in enumerate(self.client.window.descendants()):
                try:
                    text = self._get_element_text(elem)
                    aid = self._get_automation_id(elem)
                    if text or aid:
                        logger.debug("  [%d] aid=%r text=%r", idx, aid, text)
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Could not dump %s controls: %s", label, exc)

    def _click_open_button(self, dialog_window=None, timeout: float = 3.0) -> bool:
        """Click the dialog's Open button if it appears.

        If dialog_window is given, search within that window;
        otherwise search within self.client.window.
        """
        target = dialog_window or self.client.window
        if target is None:
            return False
        deadline = time.time() + timeout
        # The exact button text in the current WeChat build
        labels = {
            "open", "打开", "開啟", "開", "开",
            "open red packet", "领取红包", "领取", "開紅包", "领红包",
        }
        while time.time() < deadline:
            try:
                for elem in target.descendants():
                    text = self._get_element_text(elem).lower()
                    # Check exact match or substring
                    if text in labels or any(label in text for label in labels):
                        if self._click_if_visible(elem):
                            time.sleep(0.5)
                            return True
                    # Also try matching the element class / aid for "Open" buttons
                    try:
                        ea = elem.automation_id() or ""
                        ect = elem.element_info.control_type or ""
                        if any(kw in ea.lower() for kw in ["open", "领取", "打开"]) and ect in ("Button", "Text", "Hyperlink"):
                            if self._click_if_visible(elem):
                                time.sleep(0.5)
                                return True
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def _wait_for_main_view(self, timeout: float = 3.0) -> bool:
        """Wait until the overlay Open button is gone (dialog dismissed)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                w = self.client.window
                if w is None:
                    time.sleep(0.3)
                    continue
                for elem in w.descendants():
                    try:
                        txt = (elem.window_text() or "").lower()
                        ct = elem.element_info.control_type or ""
                        if ct == "Button" and txt in ("open", "打开", "领取", "领取红包", "领红包", "开"):
                            break  # overlay still present
                    except Exception:
                        continue
                else:
                    return True  # no overlay button found
            except Exception:
                pass
            time.sleep(0.3)
        return True  # timeout — assume gone

    def _confirm_and_close(self) -> bool:
        """Handle the red-packet detail dialog by opening it and then closing it.

        Returns True only if the dialog was found and the Open button was clicked.
        """
        dialog = self._wait_for_any_dialog(timeout=1.5)
        if dialog is None:
            logger.debug("Red packet dialog not detected after click.")
            self.client.close_red_packet_dialog()
            return False

        logger.debug("Red packet detail dialog detected.")
        time.sleep(0.5)

        opened = self._click_open_button(dialog_window=dialog, timeout=2.0)
        if not opened:
            logger.debug("Could not find Open button on dialog.")
        else:
            logger.debug("Open button clicked successfully.")

        time.sleep(0.8)
        logger.debug("Closing the detail dialog.")
        self.client.close_red_packet_dialog()
        self._wait_for_main_view(timeout=3.0)

        return opened

    @property
    def reached_cap(self) -> bool:
        return self.collected >= self.max_per_run
