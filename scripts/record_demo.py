#!/usr/bin/env python3
"""Record a narrated video walkthrough of the Banking Service dashboard.

Launches a real server, drives the browser through the complete user journey
at a reviewable pace, and saves the recording as an MP4 in docs/videos/.

Usage:
    uv run --with playwright,httpx scripts/record_demo.py

Requires: playwright browsers installed (playwright install chromium)
          ffmpeg for WebM→MP4 conversion
"""

import multiprocessing
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "demo_recording.db")
VIDEO_DIR = os.path.join(ROOT, "docs", "videos")
BASE_URL = "http://127.0.0.1:8899"

DEMO_EMAIL = "demo@bankingservice.dev"
DEMO_PASSWORD = "DemoPass123!"


def _run_server():
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.abspath(DB_PATH)}"
    os.environ["JWT_SECRET_KEY"] = "demo-recording-secret"
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8899, log_level="warning")


def wait_for_server():
    import httpx
    for _ in range(40):
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=1)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def pause(seconds=1.5):
    """Deliberate pause so the video is easy to follow."""
    time.sleep(seconds)


def record():
    from playwright.sync_api import sync_playwright

    os.makedirs(VIDEO_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=300)
        context = browser.new_context(
            record_video_dir=VIDEO_DIR,
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # ── 1. Landing page ──────────────────────────────────────────
        print("  1/12  Loading dashboard...")
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        pause(2)

        # ── 2. Sign up ───────────────────────────────────────────────
        print("  2/12  Signing up...")
        page.locator("#auth-tab-signup").click()
        pause(0.5)
        page.locator("#signup-email").fill(DEMO_EMAIL)
        pause(0.5)
        page.locator("#signup-password").fill(DEMO_PASSWORD)
        pause(0.5)
        page.locator("#btn-signup").click()
        pause(2)

        # ── 3. Log in ────────────────────────────────────────────────
        print("  3/12  Logging in...")
        page.locator("#login-email").fill(DEMO_EMAIL)
        pause(0.5)
        page.locator("#login-password").fill(DEMO_PASSWORD)
        pause(0.5)
        page.locator("#btn-login").click()
        pause(2)

        # ── 4. Create profile ────────────────────────────────────────
        print("  4/12  Creating profile...")
        page.locator("#pf-first").fill("Demo")
        pause(0.3)
        page.locator("#pf-last").fill("User")
        pause(0.3)
        page.locator("#pf-dob").fill("1990-06-15")
        pause(0.3)
        page.locator("#btn-profile").click()
        pause(3)

        # ── 5. Create checking account ───────────────────────────────
        print("  5/12  Creating checking account...")
        page.evaluate("showTab('accounts')")
        pause(1)
        page.locator("#new-acct-type").select_option("checking")
        pause(0.5)
        page.locator("button:has-text('Open Account')").click()
        pause(2)

        # ── 6. Create savings account ────────────────────────────────
        print("  6/12  Creating savings account...")
        page.locator("#new-acct-type").select_option("savings")
        pause(0.5)
        page.locator("button:has-text('Open Account')").click()
        pause(2)

        # ── 7. Deposit $5,000 ────────────────────────────────────────
        print("  7/12  Depositing $5,000...")
        page.evaluate("showTab('transfers')")
        pause(1)
        page.locator("#dep-amt").fill("5000.00")
        pause(0.5)
        page.locator("#xfer-deposit button.btn-success").click()
        pause(2)

        # ── 8. Transfer $1,000 ───────────────────────────────────────
        print("  8/12  Transferring $1,000...")
        page.evaluate("showXferTab('transfer')")
        pause(1)
        # Select savings as destination (from defaults to checking)
        page.locator("#xfer-to").select_option(index=1)
        pause(0.3)
        page.locator("#xfer-amt").fill("1000.00")
        pause(0.5)
        page.locator("#xfer-transfer button.btn-primary").click()
        pause(2)

        # ── 9. Issue card + card spend ───────────────────────────────
        print("  9/12  Issuing card and spending $75.50...")
        page.evaluate("showTab('cards')")
        pause(1)
        page.locator("button:has-text('Issue Card')").click()
        pause(2)
        page.locator("#spend-amt").fill("75.50")
        page.locator("#spend-merch").fill("Downtown Bistro")
        pause(0.5)
        page.locator("button:has-text('Charge Card')").click()
        pause(2)

        # ── 10. Generate statement ───────────────────────────────────
        print(" 10/12  Generating statement...")
        page.evaluate("showTab('statements')")
        pause(1)
        page.locator("button:has-text('Generate Statement')").click()
        pause(2)

        # ── 11. Dashboard overview + dark mode + ops panel ───────────
        print(" 11/12  Dashboard overview, dark mode, ops panel...")
        page.evaluate("showTab('dashboard')")
        pause(2)

        # Toggle dark mode
        page.locator("#theme-toggle").click()
        pause(2)

        # Open ops panel
        page.locator("#ops-toggle").click()
        pause(2)

        # Close ops panel
        page.locator("#ops-toggle").click()
        pause(1)

        # Toggle back to light
        page.locator("#theme-toggle").click()
        pause(1)

        # ── 12. Logout ───────────────────────────────────────────────
        print(" 12/12  Logging out...")
        page.locator("#logout-btn").click()
        pause(2)

        # Finalize video
        video_path = page.video.path()
        context.close()
        browser.close()

    # Convert WebM → MP4
    if shutil.which("ffmpeg") and video_path and os.path.exists(video_path):
        mp4_path = os.path.join(VIDEO_DIR, "banking-demo-walkthrough.mp4")
        print(f"\n  Converting to MP4: {mp4_path}")
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-preset", "fast",
             "-crf", "23", "-an", mp4_path],
            capture_output=True,
        )
        if os.path.exists(mp4_path):
            os.remove(video_path)
            size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
            print(f"  Done! {size_mb:.1f} MB → {mp4_path}")
        else:
            print(f"  ffmpeg conversion failed, WebM kept at: {video_path}")
    else:
        print(f"\n  Video saved as WebM: {video_path}")
        print("  Install ffmpeg to auto-convert to MP4.")

    return video_path


def main():
    print("Banking Service Demo Recording")
    print("=" * 50)

    # Clean up old DB
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"]:
        if os.path.exists(f):
            os.unlink(f)

    # Start server
    print("\nStarting server...")
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()

    if not wait_for_server():
        proc.terminate()
        print("ERROR: Server failed to start")
        sys.exit(1)

    print("Server ready.\n")
    print("Recording demo walkthrough (1920×1080, ~45s)...\n")

    try:
        record()
    finally:
        proc.terminate()
        proc.join(timeout=5)
        for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"]:
            if os.path.exists(f):
                os.unlink(f)

    print("\nDone!")


if __name__ == "__main__":
    main()
