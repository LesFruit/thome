#!/usr/bin/env python3
"""Seed development database with sample data for demos.

Usage: uv run scripts/seed_data.py
"""
# /// script
# dependencies = ["sqlalchemy"]
# ///

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("Seed script placeholder — will populate demo data once models are built.")


if __name__ == "__main__":
    main()
