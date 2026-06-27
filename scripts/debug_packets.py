"""Debug red-packet detection and rectangle APIs (read-only)."""

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.redpacket_finder import find_red_packets_in_current_chat  # noqa: E402
from src.ui_scan import find_by_auto_id  # noqa: E402
from src.wechat_client import WeChatClient  # noqa: E402


def rect_info(rect):
    def read(name):
        value = getattr(rect, name, 0)
        return value() if callable(value) else value

    left = read("left")
    top = read("top")
    right = read("right")
    bottom = read("bottom")
    return left, top, right, bottom, right - left, bottom - top


def main():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    client = WeChatClient(title=config.get("wechat_window_title", "WeChat"))
    if not client.connect(timeout=15):
        print("connect failed")
        return 1

    group = config["selected_groups"][0]
    print("select:", client.select_chat(group))
    time.sleep(2.5)

    message_list = find_by_auto_id(client.window, "chat_message_list", timeout=10)
    print("message_list:", message_list is not None)

    packets = find_red_packets_in_current_chat(client.window)
    print("candidates:", len(packets))

    for index, packet in enumerate(packets):
        left, top, right, bottom, width, height = rect_info(packet.rectangle())
        text = (packet.window_text() or "")[:100]
        aid = (packet.automation_id() or "")[:80]
        print(f"[{index}] {width}x{height} at ({left},{top}) aid={aid!r}")
        print(f"      text={text!r}")
        try:
            packet.rectangle().width()
            print("      width() callable: yes")
        except TypeError as exc:
            print(f"      width() callable: NO ({exc})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
