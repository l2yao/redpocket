# WeChat Bot — Windows UI Automation

A config-driven Python bot that drives the WeChat for Windows desktop client via
UI Automation (UIA). Define actions in `config.json` — the bot runs them on a
loop, respecting each action's interval.

> **Disclaimer:** WeChat does not provide a public API for this. The script drives
> the UI directly — use at your own risk.

---

## Quick Start

```bash
pip install -r requirements.txt
# Start WeChat and log in first, then:
python run.py
```

That's it. The bot reads `config.json` and runs all enabled actions in a loop.

---

## Configuration

Edit `config.json`:

```json
{
  "tick_interval": 2,
  "wechat_window_title": "WeChat",
  "actions": [
    {
      "type": "redpacket",
      "target": "Group Name",
      "interval_seconds": 30,
      "enabled": true
    },
    {
      "type": "message",
      "target": "Contact Name",
      "interval_seconds": 3600,
      "message": "Your scheduled message",
      "enabled": true
    }
  ]
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `tick_interval` | 2 | Seconds between each check of the action list |
| `wechat_window_title` | "WeChat" | Window title to match |
| `actions` | [] | Array of action definitions |

### Action fields

| Field | Default | Description |
|-------|---------|-------------|
| `type` | `"message"` | `"redpacket"` or `"message"` |
| `target` | — | Group or contact name (must appear in WeChat chat list) |
| `interval_seconds` | 60 | How often to run this action |
| `message` | `""` | Text to send (required for type `"message"`) |
| `enabled` | `true` | Set `false` to pause without deleting |

---

## CLI

```bash
# Default — run the config-driven bot loop
python run.py

# Or explicitly
python run.py run
python run.py run --dry-run      # print actions without connecting

# One-off commands (still available)
python run.py send "文件传输助手" "Hello!"
python run.py broadcast "Hi all" --groups "Group A" "Group B"
python run.py collect --groups "Family" --once
python run.py list
```

---

## Project Structure

```
wechat-bot/
├── run.py                  # Quick entry: python run.py
├── config.json             # Action definitions
├── requirements.txt
├── README.md
└── src/
    ├── cli.py              # CLI entry and dispatch
    ├── config.py           # Config + Action dataclass
    ├── client.py           # WeChatClient (uiautomation-based)
    ├── runner.py           # BotRunner — the config-driven loop
    ├── actions/
    │   ├── __init__.py
    │   ├── messenger.py    # Message sending
    │   └── redpacket.py    # Red packet collection
    └── ui/
        ├── scanner.py      # UI tree helpers
        └── selector.py     # Interactive group picker
```

---

## Adding a New Action Type

1. Create `src/actions/your_feature.py`
2. Implement a class (or function) taking `WeChatClient`
3. Add the type to `Action` in `src/config.py`
4. Wire execution in `BotRunner._execute()` in `src/runner.py`

---

## Troubleshooting

- **"Could not find WeChat window"** — Start WeChat and log in first.
- **"No actions defined"** — Add at least one action to `config.json`.
- **Action never fires** — Make sure `enabled: true` and WeChat is running.
- **Red packets not detected** — WeChat's UI strings change across versions.
  Update `RED_PACKET_HINTS` in `src/actions/redpacket.py` if needed.
