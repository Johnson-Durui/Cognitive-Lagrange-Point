#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"
exec python3 server.py --host 127.0.0.1 --port 4173
