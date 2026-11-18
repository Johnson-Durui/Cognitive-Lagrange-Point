#!/usr/bin/env python3
"""Cross-platform launcher for Cognitive Lagrange Point (Windows / macOS / Linux)."""

from __future__ import annotations

import webbrowser
from threading import Timer

from backend.app import build_arg_parser, main as run_backend
from backend.shared import get_demo_status


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    parser.add_argument(
        "--open",
        action="store_true",
        help="Automatically open the web console in the default browser on startup",
    )
    args, remaining = parser.parse_known_args(argv)
    if args.open:
        url = f"http://{args.host}:{args.port}"
        Timer(1.2, lambda: webbrowser.open(url)).start()

    forwarded: list[str] = ["--host", args.host, "--port", str(args.port)]
    if args.demo:
        forwarded.append("--demo")
    if args.reload:
        forwarded.append("--reload")
    forwarded.extend(remaining)
    _ = get_demo_status()
    run_backend(forwarded)


if __name__ == "__main__":
    main()
