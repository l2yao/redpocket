"""Check whether red-packet UI appears inside the main WeChat window after click."""

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pyautogui  # noqa: E402

from src.redpacket_finder import find_red_packets_in_current_chat  # noqa: E402
from src.ui_scan import find_by_auto_id  # noqa: E402
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


def find_red_packet_ui(window):
    hits = []
    for elem in window.descendants():
        try:
            aid = elem.automation_id() or ""
            text = (elem.window_text() or "").replace("\n", " ")[:60]
            blob = f"{aid} {text}".lower()
            if any(k in blob for k in ["payredenvelop", "红包", "red packet", "open", "打开", "开"]):
                hits.append((aid[:70], text))
        except Exception:
            continue
    return hits


def main():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        config = json.load(f)

    client = WeChatClient(title=config.get("wechat_window_title", "WeChat"))
    client.connect(timeout=15)
    client.close_red_packet_dialog()
    group = config["selected_groups"][0]

    for attempt in range(3):
        if client.select_chat(group):
            break
        time.sleep(1)

    for _ in range(10):
        if find_by_auto_id(client.window, "chat_message_list", timeout=2, max_nodes=500):
            break
        time.sleep(0.5)

    client.window.set_focus()
    time.sleep(0.5)

    packets = find_red_packets_in_current_chat(client.window)
    print("candidates:", len(packets))
    if not packets:
        return 1

    packet = packets[0]
    cx, cy = rect_center(packet.rectangle())
    print("before:", find_red_packet_ui(client.window)[:8])

    methods = [
        ("click_input", lambda: packet.click_input()),
        ("pyautogui", lambda: pyautogui.click(cx, cy)),
        ("double_click_input", lambda: packet.double_click_input()),
        ("pyautogui_double", lambda: pyautogui.doubleClick(cx, cy)),
    ]

    for name, action in methods:
        print(f"\n--- trying {name} at ({cx},{cy}) ---")
        client.window.set_focus()
        time.sleep(0.3)
        action()
        time.sleep(1.5)
        hits = find_red_packet_ui(client.window)
        print("matches:", hits[:12])
        if any("payredenvelop" in (h[0] or "").lower() for h in hits):
            print("DETAIL VIEW DETECTED")
            pyautogui.press("escape")
            time.sleep(0.5)
            break
        pyautogui.press("escape")
        time.sleep(0.5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
