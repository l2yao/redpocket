import unittest

from src.ui_scan import find_by_auto_id, iter_descendants_bounded


class FakeElement:
    def __init__(self, automation_id="", children=None):
        self._automation_id = automation_id
        self._children = children or []

    def automation_id(self):
        return self._automation_id

    def children(self):
        return self._children

    def descendants(self):
        for child in self._children:
            yield child
            yield from child.descendants()


class UiScanTests(unittest.TestCase):
    def test_find_by_auto_id_finds_nested_element(self):
        target = FakeElement(automation_id="session_list")
        root = FakeElement(children=[FakeElement(children=[target])])

        found = find_by_auto_id(root, "session_list", timeout=1.0)

        self.assertIs(found, target)

    def test_iter_descendants_bounded_respects_node_limit(self):
        leaf = FakeElement(automation_id="leaf")
        root = FakeElement(children=[leaf])

        nodes = list(iter_descendants_bounded(root, max_nodes=1))

        self.assertEqual([leaf], nodes)


if __name__ == "__main__":
    unittest.main()
