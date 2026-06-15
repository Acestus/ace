#!/usr/bin/env python3
"""render_progress_bar.py — Render a compact 20-block progress bar."""

from __future__ import annotations

import argparse


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def render(value: int, width: int, filled: str, empty: str) -> str:
    filled_count = round((clamp(value, 0, 100) / 100) * width)
    return f"{filled * filled_count}{empty * (width - filled_count)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a progress bar")
    parser.add_argument("--value", type=int, required=True, help="Progress value from 0 to 100")
    parser.add_argument("--width", type=int, default=20, help="Number of blocks to render")
    parser.add_argument("--filled", default="■", help="Filled block character")
    parser.add_argument("--empty", default="□", help="Empty block character")
    parser.add_argument("--label", default="Confidence", help="Label to prefix the bar")
    args = parser.parse_args()

    bar = render(args.value, args.width, args.filled, args.empty)
    print(f"{args.label}: [{bar}] {clamp(args.value, 0, 100)}%")


if __name__ == "__main__":
    main()
