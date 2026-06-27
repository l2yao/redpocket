"""Inspect the WeChat UI tree for red-packet elements (with encoding-safe output)."""
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.wechat_client import WeChatClient
from src.redpacket_finder import _find_message_list
from src.ui_scan import find_by_auto_id, iter_descendants_bounded

client = WeChatClient(title='WeChat')
client.connect(timeout=10)
client.select_chat('🐂🐑🐖無量壽素食🥒群2')
time.sleep(2)

# Find message list by known automation ID
ml = _find_message_list(client.window)
print('_find_message_list result:', ml)

# Also search for any element whose ID contains "message" or "chat"
print('\n=== Elements with message/chat in automation_id ===')
count = 0
for e in iter_descendants_bounded(client.window, max_nodes=2000):
    try:
        aid = e.automation_id() or ''
    except Exception:
        aid = ''
    if 'message' in aid.lower() or 'chat' in aid.lower():
        txt = ''
        try:
            txt = (e.window_text() or '')[:60]
        except Exception:
            txt = '<encoding error>'
        print(f'  aid={aid[:80]} text={txt!r}')
        count += 1
        if count > 30:
            break

if count == 0:
    print('  (none found)')

# If message list was found, show red-packet related descendants
if ml is not None:
    print('\n=== Red-packet related elements in message list ===')
    count = 0
    for e in ml.descendants():
        try:
            txt = (e.window_text() or '')
        except Exception:
            txt = ''
        try:
            aid = (e.automation_id() or '')
        except Exception:
            aid = ''
        blob = (txt + ' ' + aid).lower()
        if any(k in blob for k in ['红包', 'red', 'packet', 'chat_bubble', 'message', 'bubble', 'wechat']):
            try:
                print(f'  aid={aid[:60]} txt={txt[:80]}')
            except Exception:
                print(f'  aid={aid[:60]} txt=<encoding error>')
            count += 1
            if count > 10:
                break
    if count == 0:
        print('  (no red-packet related elements)')
