# WeChat Bot — Windows UI Automation

A Python bot that drives the WeChat for Windows desktop client via UI Automation (UIA).
Supports **sending messages** (individual and broadcast) and **collecting red packets**
from monitored groups.

> **Disclaimer:** WeChat does not provide a public API for this. The script drives
> the UI directly — use at your own risk.

---

## Features

| Command | Description |
|---------|-------------|
| `send` | Send a DM to any group or contact |
| `broadcast` | Send the same message to multiple targets |
| `collect` | Poll selected groups for red packets and auto-open them |
| `list` | Print all conversations visible in the chat list |

---

## Requirements

- Windows 10/11
- WeChat for Windows **running and logged in**
- Python 3.10+

## Install

```bash
pip install -r requirements.txt
```

## Usage

WeChat must be open and logged in before running any command.

```bash
# Send a message
python run.py send "文件传输助手" "Hello from WeChat Bot!"

# Broadcast to groups configured in config.json
python run.py broadcast "Good morning everyone!" --groups "Family" "Work Group"

# List all conversations
python run.py list

# Collect red packets (interactive group selection)
python run.py collect

# Collect from specific groups, scan once
python run.py collect --groups "Group A" "Group B" --once

# Collect with polling (default: every 5s, cap: 10 packets)
python run.py collect --poll 3 --max 20
```

### Shortcuts

```bash
python -m src.cli send "文件传输助手" "hello"
python -m src.main send "文件传输助手" "hello"   # backward-compatible
```

---

## Project Structure

```
wechat-bot/
├── run.py                  # Quick entry: python run.py <command>
├── config.json             # Persistent configuration
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI argument parser and dispatch
│   ├── main.py             # Backward-compat alias → cli.py
│   ├── client.py           # WeChatClient — window control, send, select chat
│   ├── config.py           # Config loading/saving from config.json
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── messenger.py    # Message sending (single + broadcast)
│   │   └── redpacket.py    # RedPacketCollector — find & open red packets
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── scanner.py      # UI tree helpers (find by auto_id/text, click)
│   │   └── selector.py     # Interactive group selection
│   └── utils/
│       ├── __init__.py
│       └── text.py         # Mojibake repair, text normalization
├── tests/                  # Unit tests (legacy)
└── scripts/                # Debug scripts (legacy)
```

### Architecture

- **`client.py`** — Core layer. Connects to the WeChat window via `uiautomation`.
  Uses keyboard shortcuts (Ctrl+F search, Enter to open chat) as fallback when
  the new (mmui/Qt-based) WeChat version lacks UIA automation IDs.
- **`actions/`** — Modular action plugins. Each file implements one capability.
  Add new `.py` files here for future features (e.g. `moments.py`, `auto_reply.py`).
- **`cli.py`** — Single entry point. Subcommands dispatch to the correct action.
- **`ui/scanner.py`** — Low-level UIA tree traversal with timeouts and node limits.

### Adding a New Action

1. Create `src/actions/your_feature.py`
2. Implement a class that takes `WeChatClient` in its constructor
3. Add a subcommand in `src/cli.py::build_parser()`
4. Wire the handler in `src/cli.py::main()`

---

## Configuration

Edit `config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `poll_interval_seconds` | 5 | Time between red-packet scans |
| `max_redpockets_per_run` | 10 | Stop after this many |
| `selected_groups` | [] | Persisted after interactive collect |
| `wechat_window_title` | "WeChat" | Window title to match |

---

## Troubleshooting

- **"Could not find WeChat window"** — Start WeChat and log in first.
- **Message sending fails** — Make sure the target contact/group exists in your
  recent chats list. The bot uses Ctrl+F to search — if the contact is hidden,
  try adding them to your chat list first.
- **Red packets not detected** — WeChat's UI strings change across versions.
  Update `RED_PACKET_HINTS` in `src/actions/redpacket.py` if needed.
- **UIA elements not found** — WeChat 4.0+ (WeChatAppEx) uses a custom Qt/mmui
  framework that limits UIA accessibility. The bot falls back to keyboard
  shortcuts, but some features may need adjustments per version.
