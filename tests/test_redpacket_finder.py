import unittest

from src.redpacket_finder import find_red_packets_in_current_chat


class FakeElement:
    def __init__(self, automation_id="", text="", children=None, legacy=None):
        self._automation_id = automation_id
        self._children = children or []
        self._text = text
        self._legacy = legacy or {}

    def automation_id(self):
        return self._automation_id

    def window_text(self):
        return self._text

    def children(self):
        return self._children

    def descendants(self):
        for child in self._children:
            yield child
            yield from child.descendants()

    def legacy_properties(self):
        return self._legacy


class FakeWindow:
    def __init__(self, descendants):
        self._descendants = descendants

    def descendants(self):
        for elem in self._descendants:
            yield elem
            yield from elem.descendants()


class RedPacketFinderTests(unittest.TestCase):
    def test_finds_packet_from_descendant_text(self):
        packet = FakeElement(
            automation_id="packet_button", text="", legacy={"Value": "查看红包"}
        )
        bubble = FakeElement(
            automation_id="chat_bubble_item_view", text="", children=[packet]
        )
        message_list = FakeElement(
            automation_id="chat_message_list", children=[bubble, packet]
        )
        window = FakeWindow([message_list])

        packets = find_red_packets_in_current_chat(window)

        self.assertEqual([packet], packets)

    def test_returns_empty_when_message_list_missing(self):
        window = FakeWindow([])

        packets = find_red_packets_in_current_chat(window)

        self.assertEqual([], packets)


if __name__ == "__main__":
    unittest.main()
