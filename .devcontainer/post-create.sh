#!/usr/bin/env bash
set -euo pipefail

sudo mkdir -p /home/dev/.claude /home/dev/.config/gh
sudo chown -R dev:dev /home/dev/.claude /home/dev/.config/gh

[ -f /home/dev/.claude/settings.json ] || echo '{"sandbox": {"enabled": false}}' > /home/dev/.claude/settings.json

npm install -g @anthropic-ai/claude-code

pip install --user -r requirements.txt
python3 -m playwright install --with-deps chromium
