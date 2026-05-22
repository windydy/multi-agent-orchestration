#!/usr/bin/env python3
"""Quick debug: check if assets load correctly."""
from playwright.sync_api import sync_playwright
import subprocess, time, os

DIR = "/Users/windydy/Working/multi-agent-orchestration"
os.chdir(DIR)

# Start server
env = os.environ.copy()
env["PYTHONPATH"] = DIR
proc = subprocess.Popen(
    [".venv/bin/python", "scripts/dashboard.py", "--port", "8000"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env
)
time.sleep(3)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Listen for failed requests
    page.on("response", lambda r: print(f"  {r.status} {r.url}"))

    page.goto("http://127.0.0.1:8000/", wait_until="domcontentloaded", timeout=10000)
    time.sleep(2)

    # Check if CSS loaded
    styles = page.evaluate("() => document.styleSheets.length")
    print(f"Stylesheets loaded: {styles}")

    # Check computed bg
    bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    print(f"Body bg: {bg}")

    # Check if Tailwind classes applied
    header = page.query_selector("header")
    if header:
        classes = header.get_attribute("class")
        print(f"Header classes: {classes}")
        bg = page.evaluate("el => getComputedStyle(el).backgroundColor", header)
        print(f"Header bg: {bg}")

    page.screenshot(path="/tmp/debug-dashboard.png", full_page=True)
    browser.close()

proc.terminate()
print("Screenshot: /tmp/debug-dashboard.png")
