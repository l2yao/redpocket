# RedPocket — Auto-collect WeChat Red Packets (Windows)

A Python + pywinauto bot that watches selected WeChat groups and automatically
opens red packets for you.

> **Disclaimer:** WeChat does not provide a public API for this. The script
> drives the UI directly, which is fragile and may violate WeChat's Terms of
> Service. Use at your own risk.

## Prerequisites

- Windows 10/11
- WeChat for Windows **running and logged in**
- Python 3.10+

## Setup

```bash
cd c:\Users\Long\Documents\redpocket
python -m pip install -r requirements.txt
```

## Usage

```bash
# Interactive mode — pick groups from a list
python -m src.main

# Or specify groups directly
python -m src.main --groups "Family" "Work Chat"

# One-shot scan (no polling loop)
python -m src.main --groups "Family" --once

# Custom poll interval and cap
python -m src.main --poll 3 --max 5
```

## Configuration

Edit `config.json` to change defaults:

| Key | Default | Description |
|---|---|---|
| `poll_interval_seconds` | 5 | Time between scans |
| `max_redpockets_per_run` | 10 | Stop after this many |
| `require_confirmation` | true | Prompt before each click (reserved) |
| `selected_groups` | [] | Persisted after first interactive run |

## How It Works

1. `pywinauto` connects to the running WeChat window.
2. The user selects groups via CLI.
3. On each poll cycle the script opens each group, scans the message pane for
   red-packet bubbles (matched by accessibility text), and clicks them.
4. The red-packet dialog is confirmed and closed.
5. The loop repeats until the per-run cap is hit or the user presses Ctrl+C.

## Troubleshooting

- **"WeChat is not running"** — start WeChat and log in first.
- **No red packets detected** — WeChat's UI strings change between versions.
  Update `RED_PACKET_HINTS` in `src/redpacket_finder.py` to match your client.
- **Wrong element clicked** — run with `logging.DEBUG` to see what the script
  is targeting, and adjust the matcher accordingly.
