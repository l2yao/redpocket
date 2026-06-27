import unittest
from unittest.mock import patch

from src.wechat_client import WeChatClient


class FakeRect:
    def __init__(self, left=0, top=0, right=10, bottom=10):
        self._left = left
        self._top = top
        self._right = right
        self._bottom = bottom

    def left(self):
        return self._left

    def right(self):
        return self._right

    def top(self):
        return self._top

    def bottom(self):
        return self._bottom


class FakeItem:
    def __init__(self, automation_id="", text=""):
        self._automation_id = automation_id
        self._text = text
        self._rect = FakeRect()
        self.clicked = False

    def automation_id(self):
        return self._automation_id

    def window_text(self):
        return self._text

    def rectangle(self):
        return self._rect

    def click_input(self):
        self.clicked = True

    def descendants(self):
        return []


class FakeSessionList:
    def __init__(self, items):
        self._items = items

    def automation_id(self):
        return "session_list"

    def children(self):
        return self._items

    def wrapper_object(self):
        return self

    def descendants(self):
        for item in self._items:
            yield item


class FakeElementInfo:
    def __init__(self, class_name=""):
        self.class_name = class_name


class FakeWindow:
    def __init__(self, descendants, title="", class_name=""):
        self._descendants = descendants
        self._title = title
        self.element_info = FakeElementInfo(class_name)

    def descendants(self):
        for item in self._descendants:
            yield item
            if hasattr(item, "descendants"):
                yield from item.descendants()

    def window_text(self):
        return self._title

    def set_focus(self):
        return None

    def automation_id(self):
        return ""


class WeChatClientTests(unittest.TestCase):
    def _attach_session_list(self, client, items):
        session_list = FakeSessionList(items)
        client._session_list = session_list
        client.window = FakeWindow([session_list])

    def test_select_chat_uses_real_mouse_click(self):
        item = FakeItem(automation_id="session_item_group")
        client = WeChatClient()
        client.app = object()
        self._attach_session_list(client, [item])

        with patch("src.wechat_client.pyautogui.click") as click_mock:
            self.assertTrue(client.select_chat("group"))

        click_mock.assert_called_once()
        self.assertFalse(item.clicked)

    def test_select_chat_returns_false_when_not_connected(self):
        client = WeChatClient()
        client.window = None
        client.app = None

        with patch.object(client, "ensure_connected", return_value=False):
            self.assertFalse(client.select_chat("group"))

    def test_select_chat_falls_back_to_visible_text(self):
        item = FakeItem(text="Group Name")
        client = WeChatClient()
        client.app = object()
        self._attach_session_list(client, [item])

        with patch("src.wechat_client.pyautogui.click") as click_mock:
            self.assertTrue(client.select_chat("Group Name"))

        click_mock.assert_called_once()
        self.assertFalse(item.clicked)

    def test_select_chat_matches_normalized_visible_text(self):
        item = FakeItem(text="Group   Name")
        client = WeChatClient()
        client.app = object()
        self._attach_session_list(client, [item])

        with patch("src.wechat_client.pyautogui.click") as click_mock:
            self.assertTrue(client.select_chat("GroupName"))

        click_mock.assert_called_once()
        self.assertFalse(item.clicked)

    def test_find_main_window_falls_back_to_title_match(self):
        matching_window = FakeWindow([FakeItem()], title="WeChat")
        client = WeChatClient()

        with patch("src.wechat_client.Desktop") as desktop_cls:
            desktop_cls.return_value.windows.return_value = [matching_window]
            self.assertIs(client._find_main_window(), matching_window)


if __name__ == "__main__":
    unittest.main()
