#!/bin/bash
# verify_memory_search.sh
# 端到端验证新增的 AgentMemory 查询 API

set -e

PORT=8100
echo "Starting API server on port $PORT..."
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

# 尝试启动 API server（如果已在运行则跳过）
if ! curl -s -o /dev/null -w "" http://localhost:$PORT/api/health 2>/dev/null; then
    .venv/bin/python -m uvicorn src.api.server:app --port "$PORT" &
    SERVER_PID=$!
    sleep 3

    cleanup() {
        kill $SERVER_PID 2>/dev/null || true
    }
    trap cleanup EXIT
fi

PASS_COUNT=0
FAIL_COUNT=0

# 测试 1：API 端点返回 200
echo -n "Test 1: API endpoint returns 200 ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:$PORT/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then
  echo "PASS"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "FAIL (got $STATUS)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# 测试 2：返回正确字段
echo -n "Test 2: Response has required fields ... "
BODY=$(curl -s \
  -X POST http://localhost:$PORT/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' 2>/dev/null || echo '{}')
echo "$BODY" | .venv/bin/python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'results' in d, 'Missing results field'
assert isinstance(d['results'], list), 'results must be a list'
" 2>/dev/null
if [ $? -eq 0 ]; then
  echo "PASS"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "FAIL (missing fields)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# 测试 3：空查询返回空列表
echo -n "Test 3: Empty query returns empty list ... "
BODY=$(curl -s \
  -X POST http://localhost:$PORT/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": ""}' 2>/dev/null || echo '{}')
echo "$BODY" | .venv/bin/python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('results') == [], 'Empty query should return empty list'
" 2>/dev/null
if [ $? -eq 0 ]; then
  echo "PASS"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "FAIL (non-empty result for empty query)"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""
echo "Results: $PASS_COUNT passed, $FAIL_COUNT failed"

if [ $FAIL_COUNT -gt 0 ]; then
  echo "VERIFICATION FAILED"
  exit 1
fi

echo "All verification passed!"
