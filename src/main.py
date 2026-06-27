"""Entry point: poll selected WeChat groups and auto-collect red pockets."""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .collector import RedPacketCollector
from .group_selector import select_groups
from .wechat_client import WeChatClient

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _validate_groups(client, groups):
    """Check that each group exists in the session list without toggling the chat."""
    from .redpacket_finder import _find_message_list as _fml
    from .ui_scan import find_by_auto_id, iter_descendants_bounded

    # Check if a chat is already open
    chat_was_open = _fml(client.window, timeout=0.5) is not None

    valid = []
    chat_list = client.get_chat_list()
    if chat_list is None:
        logger.warning("Cannot access session list to validate groups.")
        return groups  # assume valid

    seen = set()
    for item in iter_descendants_bounded(chat_list, max_nodes=400):
        try:
            aid = item.automation_id() or ""
            if aid.startswith("session_item_"):
                name = aid.replace("session_item_", "")
                seen.add(name)
        except Exception:
            continue

    valid = [g for g in groups if g in seen]
    missing = [g for g in groups if g not in seen]
    if missing:
        logger.warning("Groups no longer found: %s. Re-select all groups.", missing)
        return []
    return valid


def main():
    parser = argparse.ArgumentParser(description="Auto-collect WeChat red pockets.")
    parser.add_argument(
        "--groups", nargs="*", default=None,
        help="Group names to monitor. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--poll", type=float, default=None,
        help="Override poll interval (seconds) from config.",
    )
    parser.add_argument(
        "--max", type=int, default=None,
        help="Override max red pockets per run.",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Scan once and exit (no polling loop).",
    )
    args = parser.parse_args()

    config = load_config()
    poll_interval = args.poll or config.get("poll_interval_seconds", 1)
    max_per_run = args.max or config.get("max_redpockets_per_run", 10)
    confirm = config.get("require_confirmation", True)

    client = WeChatClient(title=config.get("wechat_window_title", "WeChat"))
    if not client.connect():
        logger.warning("WeChat not found; attempting to launch.")
        if not client.launch():
            logger.error("Could not start WeChat. Please open WeChat and retry.")
            sys.exit(1)
        # Wait for WeChat to start up
        import time as _time
        _time.sleep(3)
        if not client.connect(timeout=30):
            logger.error("WeChat did not start successfully.")
            sys.exit(1)

    groups = args.groups
    if not groups:
        groups = config.get("selected_groups", [])
        # Validate persisted groups still exist (without toggling the chat)
        if groups:
            groups = _validate_groups(client, groups)
    if not groups:
        groups = select_groups(client)
        if not groups:
            logger.error("No groups selected. Exiting.")
            sys.exit(1)
        config["selected_groups"] = groups
        save_config(config)

    logger.info(
        "Monitoring %d group(s) | poll=%.1fs | cap=%d | confirm=%s",
        len(groups), poll_interval, max_per_run, confirm,
    )

    collector = RedPacketCollector(
        client=client, max_per_run=max_per_run, confirm=confirm
    )

    try:
        while not collector.reached_cap:
            for group in groups:
                if collector.reached_cap:
                    break
                logger.info("Checking group '%s'...", group)
                try:
                    collected = collector.collect_from_chat(group)
                    logger.info("Group '%s' completed with %d collection(s).", group, collected)
                except Exception:
                    logger.exception("Error collecting from '%s'.", group)

            if args.once:
                break

            if collector.reached_cap:
                break

            logger.info("Sleeping %.1fs before next scan...", poll_interval)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")

    logger.info("Done. Collected %d red pocket(s).", collector.collected)


if __name__ == "__main__":
    main()
