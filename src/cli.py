from __future__ import annotations

import argparse
import logging
import sys
import time

from .actions.messenger import Messenger
from .actions.redpacket import RedPacketCollector
from .client import WeChatClient
from .config import Config
from .ui.selector import select_groups

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _create_client(cfg: Config) -> WeChatClient:
    client = WeChatClient(title=cfg.wechat_window_title)
    if not client.connect():
        logger.error("WeChat is not running. Please start WeChat and try again.")
        sys.exit(1)
    return client


def cmd_send(args):
    cfg = Config()
    client = _create_client(cfg)
    messenger = Messenger(client)
    success = messenger.send(args.message, args.group)
    if success:
        logger.info("Message sent to '%s'", args.group)
    else:
        logger.error("Failed to send message to '%s'", args.group)
        sys.exit(1)


def cmd_broadcast(args):
    cfg = Config()
    client = _create_client(cfg)
    messenger = Messenger(client)
    targets = args.groups or cfg.selected_groups
    if not targets:
        logger.error("No groups specified. Use --groups or set selected_groups in config.json")
        sys.exit(1)
    results = messenger.send_to_multiple(args.message, targets)
    ok = sum(1 for v in results.values() if v)
    fail = sum(1 for v in results.values() if not v)
    logger.info("Broadcast complete: %d sent, %d failed", ok, fail)


def cmd_collect(args):
    cfg = Config()
    client = _create_client(cfg)
    groups = args.groups or cfg.selected_groups
    if not groups:
        groups = select_groups(client)
        if not groups:
            logger.error("No groups selected")
            sys.exit(1)
        cfg.selected_groups = groups
    poll_interval = args.poll or cfg.poll_interval
    max_per_run = args.max or cfg.max_redpockets_per_run
    collector = RedPacketCollector(client=client, max_per_run=max_per_run)
    logger.info("Monitoring %d group(s) | poll=%.1fs | cap=%d", len(groups), poll_interval, max_per_run)
    try:
        while not collector.reached_cap:
            for group in groups:
                if collector.reached_cap:
                    break
                logger.info("Checking '%s'...", group)
                try:
                    n = collector.collect_from_chat(group)
                    logger.info("'%s': %d collection(s)", group, n)
                except Exception:
                    logger.exception("Error collecting from '%s'", group)
            if args.once:
                break
            if collector.reached_cap:
                break
            logger.info("Sleeping %.1fs...", poll_interval)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    logger.info("Done. Collected %d red packet(s).", collector.collected)


def cmd_list(args):
    cfg = Config()
    client = _create_client(cfg)
    print("\n=== WeChat Conversations ===\n")
    count = 0
    for name, _ in client.list_chat_items():
        print(f"  {name}")
        count += 1
    print(f"\nTotal: {count} conversations")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wechat-bot", description="WeChat automation bot")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_send = sub.add_parser("send", help="Send a message to a group/contact")
    p_send.add_argument("group", help="Target group or contact name")
    p_send.add_argument("message", help="Message text to send")

    p_bc = sub.add_parser("broadcast", help="Send message to multiple groups/contacts")
    p_bc.add_argument("message", help="Message text")
    p_bc.add_argument("--groups", nargs="*", default=None, help="Targets (default: from config)")

    p_collect = sub.add_parser("collect", help="Monitor groups and collect red packets")
    p_collect.add_argument("--groups", nargs="*", default=None, help="Groups to monitor")
    p_collect.add_argument("--poll", type=float, default=None, help="Poll interval (s)")
    p_collect.add_argument("--max", type=int, default=None, help="Max red packets per run")
    p_collect.add_argument("--once", action="store_true", help="Scan once and exit")

    p_list = sub.add_parser("list", help="List all conversations")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)
    if args.command == "send":
        cmd_send(args)
    elif args.command == "broadcast":
        cmd_broadcast(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
