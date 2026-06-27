"""CLI-based group selector that lists WeChat conversations and lets the user pick."""

import logging
from typing import List

from .wechat_client import WeChatClient

logger = logging.getLogger(__name__)


def select_groups(client: WeChatClient) -> List[str]:
    """Print all conversations and let the user choose which groups to monitor."""
    print("\n=== WeChat Conversations ===\n")
    items = []
    for name, _wrapper in client.list_chat_items():
        items.append(name)
        print(f"  [{len(items)}] {name}")

    if not items:
        print("No conversations found. Make sure WeChat is open.")
        return []

    print("\nEnter the numbers of the groups to monitor, separated by commas.")
    print("Example: 1,3,7")
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

    print(f"\nSelected {len(selected)} group(s): {', '.join(selected)}")
    return selected
