from __future__ import annotations

import logging
from typing import List

from ..client import WeChatClient

logger = logging.getLogger(__name__)


def select_groups(client: WeChatClient) -> List[str]:
    print("\n=== WeChat Conversations ===\n")
    items = []
    for name, _wrapper in client.list_chat_items():
        items.append(name)
        print(f"  [{len(items)}] {name}")
    if not items:
        print("No conversations found. Make sure WeChat is open.")
        return []
    print("\nEnter numbers separated by commas (e.g. 1,3,7):")
    raw = input("> ").strip()
    if not raw:
        return []
    selected = []
    for token in raw.split(","):
        token = token.strip()
        if not token.isdigit():
            continue
        idx = int(token) - 1
        if 0 <= idx < len(items):
            selected.append(items[idx])
    print(f"Selected {len(selected)} group(s): {', '.join(selected)}")
    return selected
