"""Dump overlay controls after opening a red-packet bubble with click_input."""

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


def dump_matches(window):
    for elem in window.descendants():
        try:
            aid = elem.automation_id() or ""
            text = (elem.window_text() or "").replace("\n", " ")[:100]
            if not text and not aid:
                continue
            blob = f"{aid} {text}".lower()
            if any(k in blob for k in ["red packet", "红包", "open", "打开", "开", "sent by", "领取"]):
                rect = elem.rectangle()
                left = rect.left() if callable(getattr(rect, "left", None)) else rect.left
                top = rect.top() if callable(getattr(rect, "top", None)) else rect.top
                right = rect.right() if callable(getattr(rect, "right", None)) else rect.right
                bottom = rect.bottom() if callable(getattr(rect, "bottom", None)) else rect.bottom
                ctype = ""
                try:
                    ctype = elem.element_info.control_type or ""
                except Exception:
                    pass
                print(
                    f"{ctype:12} aid={aid[:60]!r} text={text!r} "
                    f"rect=({left},{top})-({right},{bottom})"
                )
        except Exception:
            continue


def main():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    client = WeChatClient(title=config.get("wechat_window_title", "WeChat"))
    client.connect(timeout=15)
    client.close_red_packet_dialog()
    client.select_chat(config["selected_groups"][0])

    for _ in range(10):
        if find_by_auto_id(client.window, "chat_message_list", timeout=2, max_nodes=500):
            break
        time.sleep(0.5)

    packets = find_red_packets_in_current_chat(client.window)
    if not packets:
        print("no packets")
        return 1

    client.window.set_focus()
    time.sleep(0.3)
    print("=== opening bubble ===")
    packets[0].click_input()
    time.sleep(1.5)
    print("=== overlay matches ===")
    dump_matches(client.window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
