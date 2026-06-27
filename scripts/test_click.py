"""Test one red-packet click and observe resulting windows (interactive)."""

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pyautogui  # noqa: E402
from pywinauto import Desktop  # noqa: E402

from src.redpacket_finder import find_red_packets_in_current_chat  # noqa: E402
from src.wechat_client import WeChatClient  # noqa: E402


def rect_center(rect):
    def read(name):
        value = getattr(rect, name, 0)
        return value() if callable(value) else value

    left = read("left")
    top = read("top")
    right = read("right")
    bottom = read("bottom")
    return (left + right) // 2, (top + bottom) // 2


def list_wechat_windows():
    rows = []
    for window in Desktop(backend="uia").windows():
        try:
            title = window.window_text() or ""
            aid = window.automation_id() or ""
            if "wechat" in title.lower() or "PayRedEnvelop" in aid or "红包" in title:
                rows.append((title, aid[:60]))
        except Exception:
            continue
    return rows


def main():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    client = WeChatClient(title=config.get("wechat_window_title", "WeChat"))
    client.connect(timeout=15)
    group = config["selected_groups"][0]
    client.select_chat(group)
    time.sleep(2)

    packets = find_red_packets_in_current_chat(client.window)
    print("candidates:", len(packets))
    if not packets:
        return 1

    packet = packets[0]
    cx, cy = rect_center(packet.rectangle())
    print("before click windows:", list_wechat_windows())
    print(f"clicking packet at ({cx}, {cy}) with pyautogui")
    pyautogui.click(cx, cy)
    time.sleep(2)
    print("after click windows:", list_wechat_windows())

    print("trying click_input on same packet")
    try:
        packet.click_input()
    except Exception as exc:
        print("click_input failed:", exc)
    time.sleep(2)
    print("after click_input windows:", list_wechat_windows())

    pyautogui.press("escape")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
