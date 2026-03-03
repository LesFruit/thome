#!/usr/bin/env python3
"""End-to-end demo client exercising the full banking API flow.

Usage: uv run scripts/test_client.py [--base-url http://localhost:8000]
"""
# /// script
# dependencies = ["httpx", "click"]
# ///

import click
import httpx
import sys


@click.command()
@click.option("--base-url", default="http://localhost:8000", help="API base URL")
def main(base_url: str):
    """Run full banking flow: signup -> holder -> account -> transfer -> card -> statement."""
    client = httpx.Client(base_url=base_url, timeout=30)

    # Step 1: Health check
    r = client.get("/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    click.echo(f"[OK] Health: {r.json()}")

    r = client.get("/ready")
    assert r.status_code == 200, f"Readiness check failed: {r.text}"
    click.echo(f"[OK] Ready: {r.json()}")

    click.echo("\n--- Demo client baseline passed ---")
    click.echo("Full flow will be implemented as API endpoints are built.")


if __name__ == "__main__":
    main()
