"""Dump structure inside a red-packet chat bubble."""

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.redpacket_finder import find_red_packets_in_current_chat  # noqa: E402
from src.wechat_client import WeChatClient  # noqa: E402


def rect_str(rect):
    def read(name):
        value = getattr(rect, name, 0)
        return value() if callable(value) else value

    left = read("left")
    top = read("top")
    right = read("right")
    bottom = read("bottom")
    return f"({left},{top})-({right},{bottom}) {right-left}x{bottom-top}"


def dump_tree(elem, depth=0, max_depth=4):
    if depth > max_depth:
        return
    try:
        aid = elem.automation_id() or ""
        text = (elem.window_text() or "").replace("\n", " ")[:80]
        ctype = ""
        try:
            ctype = elem.element_info.control_type or ""
        except Exception:
            pass
        rect = rect_str(elem.rectangle())
        prefix = "  " * depth
        print(f"{prefix}{ctype} aid={aid[:70]!r} text={text!r} rect={rect}")
    except Exception as exc:
        print("  " * depth + f"<error {exc}>")
        return
    try:
        children = elem.children()
    except Exception:
        return
    for child in children:
        dump_tree(child, depth + 1, max_depth)


def main():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    client = WeChatClient(title=config.get("wechat_window_title", "WeChat"))
    client.connect(timeout=15)
    client.window.set_focus()
    for g in config.get("selected_groups", []):
        if client.select_chat(g):
            break
    time.sleep(2.5)

    packets = find_red_packets_in_current_chat(client.window)
    print("candidates:", len(packets))
    if not packets:
        return 1

    print("=== bubble tree ===")
    dump_tree(packets[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
