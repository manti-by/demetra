#!/usr/bin/env python3
"""
Run the Demetra FastAPI ticket creation API.

Usage:
    python run_api.py [--host HOST] [--port PORT] [--reload]

Examples:
    python run_api.py
    python run_api.py --host localhost --port 8080
    python run_api.py --reload  # Enable auto-reload for development
"""

import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the Demetra FastAPI ticket creation API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    print(f"Starting Demetra API server on {args.host}:{args.port}")
    print(f"Documentation available at: http://{args.host}:{args.port}/docs")

    uvicorn.run("fastapi_app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
