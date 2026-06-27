import unittest
from unittest.mock import patch

from src.collector import RedPacketCollector


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

    def width(self):
        return self._right - self._left

    def height(self):
        return self._bottom - self._top


class FakeElement:
    def __init__(self, text="", rect=None):
        self._text = text
        self._rect = rect or FakeRect()

    def window_text(self):
        return self._text

    def rectangle(self):
        return self._rect


class FakeWindow:
    def __init__(self, descendants):
        self._descendants = descendants

    def descendants(self):
        return list(self._descendants)


class FakeClient:
    def __init__(self, window):
        self.window = window


class RedPacketCollectorTests(unittest.TestCase):
    def test_clicks_open_button_in_detail_dialog(self):
        button = FakeElement(text="Open")
        client = FakeClient(FakeWindow([button]))
        collector = RedPacketCollector(client=client, max_per_run=1, confirm=True)

        with patch("src.collector.pyautogui.click") as click_mock:
            self.assertTrue(collector._click_open_button(timeout=0.1))

        click_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
