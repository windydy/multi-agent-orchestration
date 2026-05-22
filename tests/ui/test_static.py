#!/usr/bin/env python3
"""Quick test: serve static files correctly."""
import os, sys, time, subprocess, signal

DIR = "/Users/windydy/Working/multi-agent-orchestration"
os.chdir(DIR)
sys.path.insert(0, DIR)

from src.api.server import create_app

app = create_app()
print("Routes:")
for r in app.routes:
    methods = getattr(r, 'methods', None)
    path = getattr(r, 'path', None) or getattr(r, 'path_regex', 'MOUNT')
    print(f"  {methods} {path}")

# Test with TestClient
from fastapi.testclient import TestClient

with TestClient(app) as client:
    # Test root
    r = client.get("/")
    print(f"\nGET / -> {r.status_code}")
    print(f"  Content-Type: {r.headers.get('content-type', 'N/A')}")
    print(f"  Body[:100]: {r.text[:100]}")
    
    # Test CSS
    r = client.get("/assets/index-CdFMJUxx.css")
    print(f"\nGET /assets/index.css -> {r.status_code}")
    print(f"  Content-Type: {r.headers.get('content-type', 'N/A')}")
    print(f"  Body[:100]: {r.text[:100]}")
    
    # Test JS
    r = client.get("/assets/index-vU6mZQc4.js")
    print(f"\nGET /assets/index.js -> {r.status_code}")
    print(f"  Content-Type: {r.headers.get('content-type', 'N/A')}")
