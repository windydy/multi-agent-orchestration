#!/usr/bin/env python3
"""Launch the Multi-Agent Dashboard."""

import os
import sys
import uvicorn

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.server import create_app


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Agent Dashboard")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--dev", action="store_true", help="CORS open for dev")
    args = parser.parse_args()

    app = create_app()
    print(f"\n  Dashboard running at http://{args.host}:{args.port}\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
