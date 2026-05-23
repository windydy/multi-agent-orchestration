#!/usr/bin/env python3
"""E2E UI tests for Config and Observability pages using Playwright.

Tests cover:
- Config page: tab navigation, agents list, verifiers CRUD, workflows list+YAML editor
- Observability page: page load, stats summary, period switcher, charts, tables, alerts
- Cross-page navigation: Dashboard -> Config -> Observability
- API endpoint responses for both features

Usage: python tests/ui/test_config_observability_e2e.py
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

PROJECT_DIR = "/Users/windydy/Working/multi-agent-orchestration"
HERMES_VENV_PYTHON = "/Users/windydy/.hermes/hermes-agent/venv/bin/python"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


def start_dashboard():
    os.chdir(PROJECT_DIR)
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_DIR
    proc = subprocess.Popen(
        [HERMES_VENV_PYTHON, "-m", "uvicorn", "src.api.server:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, cwd=PROJECT_DIR,
    )
    for i in range(30):
        time.sleep(0.5)
        try:
            import urllib.request
            resp = urllib.request.urlopen(f"{BASE}/api/health", timeout=2)
            if resp.status == 200:
                print(f"  ✓ Dashboard started on :{PORT}")
                return proc
        except Exception:
            continue
    print("  ✗ Dashboard failed to start")
    proc.kill()
    return None


def ss(page, name, ss_dir):
    page.screenshot(path=os.path.join(ss_dir, name), full_page=True)


def has_text(page, expected):
    """Check if expected text appears anywhere on the page."""
    body = page.inner_text("body")
    return expected.lower() in body.lower()


def test_navigation(page, ss_dir):
    """Cross-page navigation via header links."""
    results = {}
    print("\n📸 Test 1: Cross-page navigation")

    page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector("header", timeout=5000)
    ss(page, "01-nav-home.png", ss_dir)

    # Dashboard visible
    ok = has_text(page, "Dashboard")
    results["nav_home"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} nav_home")

    # Navigate to Config
    page.click("a:has-text('Config')")
    time.sleep(1)
    ss(page, "01-nav-config.png", ss_dir)
    ok = has_text(page, "Configuration")
    results["nav_to_config"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} nav_to_config")

    # Navigate to Observability
    page.click("a:has-text('Observability')")
    time.sleep(1)
    ss(page, "01-nav-obs.png", ss_dir)
    ok = has_text(page, "Observability")
    results["nav_to_obs"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} nav_to_obs")

    # Back to home
    page.click("a:has-text('Dashboard')")
    time.sleep(1)
    ss(page, "01-nav-back.png", ss_dir)
    ok = has_text(page, "Dashboard")
    results["nav_back_home"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} nav_back_home")

    return results


def test_config_page(page, ss_dir):
    """Config page: title, 3 tabs, each tab renders content."""
    results = {}
    print("\n📸 Test 2: Config page")

    page.goto(f"{BASE}/config", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector("h1", timeout=5000)

    # Title
    ok = has_text(page, "Configuration")
    results["config_title"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} config_title")

    # Tab buttons
    ok = (page.query_selector("button:has-text('Workflows')") and
          page.query_selector("button:has-text('Agents')") and
          page.query_selector("button:has-text('Verifiers')"))
    results["config_3_tabs"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} config_3_tabs")

    # Agents tab
    page.click("button:has-text('Agents')")
    time.sleep(0.5)
    ok = page.query_selector(".grid") is not None
    results["config_agents_tab"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} config_agents_tab")
    ss(page, "02-agents.png", ss_dir)

    # Verifiers tab
    page.click("button:has-text('Verifiers')")
    time.sleep(0.5)
    # Either a table, or empty-state text
    ok = (page.query_selector("table") is not None or
          has_text(page, "No verifier") or
          has_text(page, "verifier"))
    results["config_verifiers_tab"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} config_verifiers_tab")
    ss(page, "02-verifiers.png", ss_dir)

    # Workflows tab
    page.click("button:has-text('Workflows')")
    time.sleep(0.5)
    ok = has_text(page, "No workflows") or page.query_selector(".space-y-2") is not None
    results["config_workflows_tab"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} config_workflows_tab")
    ss(page, "02-workflows.png", ss_dir)

    return results


def test_config_api(page, ss_dir):
    """Config API endpoints return valid JSON with expected keys."""
    results = {}
    print("\n📸 Test 3: Config API endpoints")

    for name, path, key in [
        ("api_agents", "/api/config/agents", "agents"),
        ("api_verifiers", "/api/config/verifiers", "rules"),
        ("api_workflows", "/api/config/workflows", "workflows"),
    ]:
        page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=10000)
        body = page.inner_text("body")
        try:
            data = json.loads(body)
            ok = key in data
            results[f"api_config_{name}"] = "PASS" if ok else "FAIL"
            print(f"  {'✅' if ok else '❌'} api_config_{name}")
        except json.JSONDecodeError:
            results[f"api_config_{name}"] = "FAIL"
            print(f"  ❌ api_config_{name} (invalid JSON)")

    return results


def test_config_crud(page, ss_dir):
    """CRUD via fetch(): create verifier, update agent, upsert workflow."""
    results = {}
    print("\n📸 Test 4: Config CRUD")

    # 4a. Create verifier
    result = page.evaluate("""async () => {
        const r = await fetch('/api/config/verifiers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: 'e2e-test-cost',
                condition: 'cost_threshold',
                threshold: 1.0,
                action: 'warn',
                severity: 'medium'
            })
        });
        return { ok: r.ok, status: r.status };
    }""")
    ok = result.get("ok")
    results["crud_create_verifier"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} crud_create_verifier ({result})")

    # 4b. Verifier appears in UI
    page.goto(f"{BASE}/config", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector("h1", timeout=5000)
    page.click("button:has-text('Verifiers')")
    time.sleep(0.5)
    ss(page, "04-verifier-created.png", ss_dir)
    ok = has_text(page, "e2e-test-cost")
    results["crud_verifier_visible"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} crud_verifier_visible")

    # 4c. Update agent (use correct ID: develop_agent, not developer)
    result = page.evaluate("""async () => {
        const r = await fetch('/api/config/agents/develop_agent', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ enabled: false })
        });
        return { ok: r.ok, status: r.status };
    }""")
    ok = result.get("ok")
    results["crud_update_agent"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} crud_update_agent ({result})")

    # 4d. Upsert workflow (must include 'edges' field for validation)
    wf_yaml = "name: e2e-test-workflow\ndescription: E2E test\nnodes:\n  - name: requirements\n    agent: planner\n  - name: design\n    agent: designer\nedges:\n  - from: requirements\n    to: design\n"
    result = page.evaluate(f"""async () => {{
        const r = await fetch('/api/config/workflows/e2e-test-workflow', {{
            method: 'PUT',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ yaml_content: {json.dumps(wf_yaml)}, description: 'E2E test' }})
        }});
        return {{ ok: r.ok, status: r.status }};
    }}""")
    ok = result.get("ok")
    results["crud_upsert_workflow"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} crud_upsert_workflow ({result})")

    # 4e. Workflow appears in UI (reload page to get fresh data)
    page.goto(f"{BASE}/config", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector("h1", timeout=5000)
    page.click("button:has-text('Workflows')")
    time.sleep(1)
    ss(page, "04-workflow-created.png", ss_dir)
    ok = has_text(page, "e2e-test-workflow")
    results["crud_workflow_visible"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} crud_workflow_visible")

    return results


def test_observability_page(page, ss_dir):
    """Observability page: title, period switcher, stats, charts, table, alerts."""
    results = {}
    print("\n📸 Test 5: Observability page")

    page.goto(f"{BASE}/observability", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector("h1", timeout=5000)

    # Title
    ok = has_text(page, "Observability")
    results["obs_title"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_title")

    # Period switcher
    ok = (page.query_selector("button:has-text('24h')") and
          page.query_selector("button:has-text('7d')") and
          page.query_selector("button:has-text('30d')"))
    results["obs_period_buttons"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_period_buttons")
    ss(page, "05-obs-page.png", ss_dir)

    # Stats cards (grid with 4+ items)
    page.wait_for_selector(".grid", timeout=5000)
    cards = len(page.query_selector_all(".grid > div"))
    ok = cards >= 4
    results["obs_stats_cards"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_stats_cards ({cards})")
    ss(page, "05-obs-stats.png", ss_dir)

    # Charts (SVG elements from Recharts)
    charts = len(page.query_selector_all("svg"))
    ok = charts >= 2
    results["obs_charts"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_charts ({charts})")
    ss(page, "05-obs-charts.png", ss_dir)

    # Performance table
    ok = page.query_selector("table") is not None
    results["obs_perf_table"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_perf_table")
    ss(page, "05-obs-table.png", ss_dir)

    # Alert section
    ok = has_text(page, "Recent Alerts") or has_text(page, "No alerts")
    results["obs_alerts_section"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_alerts_section")

    return results


def test_observability_api(page, ss_dir):
    """Observability API endpoints return valid JSON."""
    results = {}
    print("\n📸 Test 6: Observability API endpoints")

    for name, path, key in [
        ("overview", "/api/observability/overview?period=24h", "total_executions"),
        ("cost", "/api/observability/cost/daily?days=1", "trends"),
        ("success_rate", "/api/observability/success-rate?days=7", "rates"),
        ("performance", "/api/observability/performance", "nodes"),
        ("failure_reasons", "/api/observability/failure-reasons", "reasons"),
        ("alerts", "/api/observability/alerts", "alerts"),
    ]:
        page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=10000)
        body = page.inner_text("body")
        try:
            data = json.loads(body)
            ok = key in data
            results[f"api_obs_{name}"] = "PASS" if ok else "FAIL"
            print(f"  {'✅' if ok else '❌'} api_obs_{name}")
            if not ok:
                print(f"      Keys: {list(data.keys())}")
        except json.JSONDecodeError:
            results[f"api_obs_{name}"] = "FAIL"
            print(f"  ❌ api_obs_{name} (invalid JSON: {body[:100]})")

    return results


def test_observability_period_switch(page, ss_dir):
    """Switch period buttons, verify no crash."""
    results = {}
    print("\n📸 Test 7: Observability period switch")

    page.goto(f"{BASE}/observability", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector("h1", timeout=5000)

    # Click 24h
    page.click("button:has-text('24h')")
    time.sleep(1)
    ss(page, "07-obs-24h.png", ss_dir)
    ok = not has_text(page, "Failed to load")
    results["obs_switch_24h"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_switch_24h")

    # Click 30d
    page.click("button:has-text('30d')")
    time.sleep(1)
    ss(page, "07-obs-30d.png", ss_dir)
    ok = not has_text(page, "Failed to load")
    results["obs_switch_30d"] = "PASS" if ok else "FAIL"
    print(f"  {'✅' if ok else '❌'} obs_switch_30d")

    return results


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║  Config & Observability - UI E2E Tests         ║")
    print("╚══════════════════════════════════════════════════╝\n")

    ss_dir = os.path.join(PROJECT_DIR, "tests", "ui", "screenshots")
    os.makedirs(ss_dir, exist_ok=True)

    print("🚀 Starting dashboard server...")
    proc = start_dashboard()
    if proc is None:
        sys.exit(1)

    all_results = {}

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            for fn in [
                test_navigation,
                test_config_page,
                test_config_api,
                test_config_crud,
                test_observability_page,
                test_observability_api,
                test_observability_period_switch,
            ]:
                all_results.update(fn(page, ss_dir))

            browser.close()

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\n🛑 Dashboard stopped")

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    passed = sum(1 for v in all_results.values() if v == "PASS")
    total = len(all_results)
    for test, result in sorted(all_results.items()):
        icon = "✅" if result == "PASS" else "❌"
        print(f"  {icon} {test}: {result}")

    print(f"\n📸 Screenshots: {ss_dir}/")
    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
