from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class Config:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    @property
    def poll_interval(self) -> float:
        return float(self.get("poll_interval_seconds", 1))

    @property
    def max_redpockets_per_run(self) -> int:
        return int(self.get("max_redpockets_per_run", 10))

    @property
    def require_confirmation(self) -> bool:
        return bool(self.get("require_confirmation", True))

    @property
    def selected_groups(self) -> list[str]:
        return list(self.get("selected_groups", []))

    @selected_groups.setter
    def selected_groups(self, groups: list[str]):
        self.set("selected_groups", groups)

    @property
    def wechat_window_title(self) -> str:
        return str(self.get("wechat_window_title", "WeChat"))
