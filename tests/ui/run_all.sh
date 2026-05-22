#!/usr/bin/env bash
set -e
cd /Users/windydy/Working/multi-agent-orchestration

# Kill existing
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1

# Start dashboard
PYTHONPATH=. .venv/bin/python scripts/dashboard.py --port 8000 > /tmp/dashboard.log 2>&1 &
DPID=$!
sleep 3

# Verify
echo "=== API health ==="
curl -sf http://127.0.0.1:8000/api/health
echo ""

echo "=== Run E2E ==="
.venv/bin/python tests/ui/run_e2e.py
RC=$?

kill $DPID 2>/dev/null || true
exit $RC
