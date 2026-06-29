from __future__ import annotations

import logging
import time
from typing import Optional

from ..client import WeChatClient

logger = logging.getLogger(__name__)


class Messenger:
    def __init__(self, client: WeChatClient):
        self.client = client
        self._current_chat: Optional[str] = None

    def send(self, text: str, chat_name: str) -> bool:
        return self.client.send_message(text, chat_name=chat_name)

    def send_to_multiple(self, text: str, chat_names: list[str]) -> dict[str, bool]:
        results = {}
        for name in chat_names:
            try:
                results[name] = self.client.send_message(text, chat_name=name)
                time.sleep(0.5)
            except Exception as e:
                logger.error("Failed to send to '%s': %s", name, e)
                results[name] = False
        return results
