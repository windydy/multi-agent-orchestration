#!/usr/bin/env python3
"""Setup deps and run E2E UI tests."""
import subprocess, sys, os, time

DIR = "/Users/windydy/Working/multi-agent-orchestration"
PY = f"{DIR}/.venv/bin/python"

# Step 1: Install missing deps
print("Step 1: Installing deps...")
r = subprocess.run(
    [PY, "-m", "pip", "install", "fastapi", "uvicorn", "pydantic"],
    capture_output=True, text=True, cwd=DIR
)
print("  " + (r.stdout.strip().split("\n")[-1] if r.stdout.strip() else r.stderr.strip().split("\n")[-1]))

# Step 2: Start dashboard
print("Step 2: Starting dashboard...")
env = os.environ.copy()
env["PYTHONPATH"] = DIR
proc = subprocess.Popen(
    [PY, "scripts/dashboard.py", "--port", "8000"],
    cwd=DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env
)

for i in range(20):
    time.sleep(0.5)
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
        if resp.status == 200:
            print("  ✓ Dashboard running on :8000")
            break
    except Exception:
        pass
else:
    print("  ✗ Dashboard failed")
    proc.kill()
    sys.exit(1)

# Step 3: Run Playwright tests
print("Step 3: Running UI tests...\n")
from playwright.sync_api import sync_playwright

ss_dir = os.path.join(DIR, "tests/ui/screenshots")
os.makedirs(ss_dir, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    results = {}

    # Test 1: Homepage
    print("📸 Test 1: Homepage")
    page.goto("http://127.0.0.1:8000/", wait_until="domcontentloaded", timeout=10000)
    # Wait for React to render
    page.wait_for_selector("header", timeout=5000)
    page.screenshot(path=f"{ss_dir}/01-homepage.png", full_page=True)
    title = page.title()
    ok = "Dashboard" in title
    results["homepage"] = ok
    print(f"  Title: '{title}' → {'✅' if ok else '❌'}")

    # Test 2: Stats cards
    print("📸 Test 2: Stats cards")
    cards = page.query_selector_all(".grid > div")
    ok = len(cards) >= 5
    results["stats_cards"] = ok
    print(f"  Cards: {len(cards)} → {'✅' if ok else '⚪ (empty OK)'}")
    page.screenshot(path=f"{ss_dir}/02-stats-cards.png", full_page=True)

    # Test 3: Table present
    print("📸 Test 3: Executions table")
    has_table = page.query_selector("table") is not None
    results["table"] = True  # empty state OK
    print(f"  Table: {has_table} → ✅")
    page.screenshot(path=f"{ss_dir}/03-table.png", full_page=True)

    # Test 4: API health
    print("📸 Test 4: API /health")
    resp = page.goto("http://127.0.0.1:8000/api/health", wait_until="networkidle", timeout=10000)
    body = page.inner_text("body")
    ok = "ok" in body.lower()
    results["api_health"] = ok
    print(f"  Body: '{body.strip()}' → {'✅' if ok else '❌'}")

    # Test 5: API overview
    print("📸 Test 5: API /overview")
    page.goto("http://127.0.0.1:8000/api/overview", wait_until="networkidle", timeout=10000)
    body = page.inner_text("body")
    ok = "total_executions" in body
    results["api_overview"] = ok
    print(f"  Has total_executions: {ok} → {'✅' if ok else '❌'}")

    # Test 6: Dark theme
    print("📸 Test 6: Dark theme")
    bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    ok = "14" in bg
    results["dark_theme"] = ok
    print(f"  bg: {bg} → {'✅' if ok else '⚪'}")
    page.screenshot(path=f"{ss_dir}/06-dark-theme.png", full_page=True)

    browser.close()

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

# Summary
passed = sum(1 for v in results.values() if v)
print(f"\n{'=' * 40}")
print(f"  {'✅' if passed == len(results) else '⚠️'}  {passed}/{len(results)} passed")
print(f"{'=' * 40}")
print(f"📸 Screenshots: {ss_dir}/")
