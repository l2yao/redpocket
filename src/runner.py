from __future__ import annotations

import logging
import time

from .actions.messenger import Messenger
from .actions.redpacket import RedPacketCollector
from .client import WeChatClient
from .config import Action, Config

logger = logging.getLogger(__name__)


class BotRunner:
    def __init__(self, client: WeChatClient, actions: list[Action]):
        self.client = client
        self.actions = [a for a in actions if a.enabled]
        self._last_run: dict[int, float] = {}
        self._messenger = Messenger(client)
        self._collector: RedPacketCollector | None = None
        self._running = True

    def stop(self):
        self._running = False

    def _ensure_collector(self) -> RedPacketCollector:
        if self._collector is None:
            self._collector = RedPacketCollector(client=self.client)
        return self._collector

    def _should_run(self, idx: int, action: Action) -> bool:
        last = self._last_run.get(idx, 0.0)
        return (time.time() - last) >= action.interval_seconds

    def _execute(self, action: Action) -> bool:
        logger.info("Executing %s on '%s'", action.type, action.target)
        try:
            if action.type == "redpacket":
                collector = self._ensure_collector()
                collected = collector.collect_from_chat(action.target)
                logger.info("Collected %d red packet(s) from '%s'", collected, action.target)
                return True
            elif action.type == "message":
                if not action.message:
                    logger.warning("No message text for action on '%s'", action.target)
                    return False
                ok = self._messenger.send(action.message, action.target)
                if ok:
                    logger.info("Message sent to '%s'", action.target)
                else:
                    logger.warning("Failed to send message to '%s'", action.target)
                return ok
            else:
                logger.warning("Unknown action type: %s", action.type)
                return False
        except Exception:
            logger.exception("Error executing %s on '%s'", action.type, action.target)
            return False

    def tick(self):
        for idx, action in enumerate(self.actions):
            if not self._running:
                return
            if self._should_run(idx, action):
                self._execute(action)
                self._last_run[idx] = time.time()

    def run(self, tick_interval: float = 2.0):
        if not self.actions:
            logger.warning("No enabled actions configured")
            return
        logger.info("Bot started with %d action(s)", len(self.actions))
        for a in self.actions:
            logger.info("  %s -> '%s' every %ds", a.type, a.target, a.interval_seconds)
        try:
            while self._running:
                self.tick()
                time.sleep(tick_interval)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        logger.info("Bot finished")
