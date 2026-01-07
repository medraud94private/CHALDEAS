"""
Archivist Full Pipeline Launcher V3
- Runs Phase 1 (CPU) + Phase 2 (GPU) + Web Dashboard concurrently
- Uses V3 scripts with entity deduplication and fixed checkpoint system
"""
import subprocess
import sys
import os
import time
import signal
import webbrowser
from pathlib import Path
from datetime import datetime
import argparse

SCRIPT_DIR = Path(__file__).parent
PYTHON = sys.executable


class ProcessManager:
    """Manages multiple subprocesses."""

    def __init__(self):
        self.processes = {}
        self.running = True

    def start_process(self, name: str, cmd: list, delay: float = 0):
        """Start a subprocess."""
        if delay > 0:
            time.sleep(delay)

        print(f"[Launcher] Starting {name}...")

        # Use CREATE_NEW_CONSOLE on Windows for separate windows
        if sys.platform == 'win32':
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            proc = subprocess.Popen(cmd)

        self.processes[name] = proc
        print(f"[Launcher] {name} started (PID: {proc.pid})")
        return proc

    def stop_all(self):
        """Stop all processes."""
        print("\n[Launcher] Stopping all processes...")
        for name, proc in self.processes.items():
            if proc.poll() is None:  # Still running
                print(f"[Launcher] Stopping {name} (PID: {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[Launcher] All processes stopped.")

    def check_status(self):
        """Check status of all processes."""
        status = {}
        for name, proc in self.processes.items():
            if proc.poll() is None:
                status[name] = "RUNNING"
            else:
                status[name] = f"EXITED ({proc.returncode})"
        return status


def main():
    parser = argparse.ArgumentParser(description="Archivist Full Pipeline Launcher V3")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit files for Phase 1")
    parser.add_argument("--reset", action="store_true",
                       help="Reset all checkpoints")
    parser.add_argument("--no-phase2", action="store_true",
                       help="Skip Phase 2 (Phase 1 only)")
    parser.add_argument("--no-dashboard", action="store_true",
                       help="Skip web dashboard")
    parser.add_argument("--no-browser", action="store_true",
                       help="Don't open browser automatically")
    parser.add_argument("--phase2-delay", type=int, default=30,
                       help="Seconds to wait before starting Phase 2 (default: 30)")
    args = parser.parse_args()

    print("=" * 60)
    print("       ARCHIVIST FULL PIPELINE LAUNCHER V3")
    print("       (Entity Deduplication + Fixed Checkpoint)")
    print("=" * 60)
    print()
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    manager = ProcessManager()

    try:
        # 1. Start Web Dashboard
        if not args.no_dashboard:
            dashboard_cmd = [PYTHON, str(SCRIPT_DIR / "dashboard_server.py")]
            manager.start_process("Dashboard", dashboard_cmd)

            # Open browser
            if not args.no_browser:
                time.sleep(1)
                webbrowser.open("http://localhost:8200")

        # 2. Start Phase 1 (V3)
        phase1_cmd = [PYTHON, str(SCRIPT_DIR / "archivist_fullscale_v3.py")]
        if args.limit:
            phase1_cmd.extend(["--limit", str(args.limit)])
        if args.reset:
            phase1_cmd.append("--reset")

        manager.start_process("Phase1", phase1_cmd, delay=2)

        # 3. Start Phase 2 (V3) with delay
        if not args.no_phase2:
            phase2_cmd = [PYTHON, str(SCRIPT_DIR / "archivist_phase2_v3.py")]
            manager.start_process("Phase2", phase2_cmd, delay=args.phase2_delay)

        print()
        print("=" * 60)
        print("  All processes started!")
        print("  Dashboard: http://localhost:8200")
        print("  Press Ctrl+C to stop all processes")
        print("=" * 60)
        print()

        # Monitor loop
        while True:
            time.sleep(10)
            status = manager.check_status()

            # Check if all main processes finished
            phase1_done = status.get("Phase1", "").startswith("EXITED")
            phase2_done = args.no_phase2 or status.get("Phase2", "").startswith("EXITED")

            if phase1_done and phase2_done:
                print("\n[Launcher] All processing complete!")
                print("[Launcher] Dashboard still running. Press Ctrl+C to exit.")

                # Keep dashboard running for viewing final results
                while True:
                    time.sleep(60)

    except KeyboardInterrupt:
        print("\n[Launcher] Interrupted by user.")

    finally:
        manager.stop_all()

    print("\n[Launcher] Done.")


if __name__ == "__main__":
    main()
