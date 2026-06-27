#!/usr/bin/env python3
"""
SSH Brute-Force Auto-Blocker

Tails /var/log/auth.log in real-time. When a source IP exceeds
THRESHOLD failed SSH logins within WINDOW seconds, it is blocked
via iptables and a structured log entry is written to BLOCKER_LOG
so Promtail/Loki/Grafana can observe every block event.

Usage:
  python blocker.py                        # live blocking
  python blocker.py --dry-run              # no iptables, safe for testing
  python blocker.py --threshold 3 --window 120
"""

import argparse
import logging
import os
import re
import subprocess
import time
from collections import defaultdict

# ── Config ─────────────────────────────────────────────────────────────────────
AUTH_LOG    = "/var/log/auth.log"
BLOCKER_LOG = "/var/log/blocker/blocker.log"
THRESHOLD   = 5      # failed attempts before block
WINDOW      = 300    # sliding window in seconds

FAIL_PATTERN = re.compile(
    r"Failed password.*?from\s+(\d{1,3}(?:\.\d{1,3}){3})"
)

# ── State ──────────────────────────────────────────────────────────────────────
blocked_ips: set[str] = set()
fail_log: dict[str, list[float]] = defaultdict(list)   # ip → [timestamps]


# ── Loggers ────────────────────────────────────────────────────────────────────
# stdout logger — visible via `docker logs blocker`
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("blocker")


def setup_file_logger(path: str) -> logging.Logger:
    """
    Separate logger that writes only to BLOCKER_LOG.
    Promtail scrapes this file; Grafana alert fires on 'BLOCKED' lines.
    propagate=False prevents double-printing to stdout.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    flog = logging.getLogger("blocker.file")
    flog.setLevel(logging.INFO)
    flog.propagate = False

    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    flog.addHandler(handler)
    return flog


# ── Core logic ─────────────────────────────────────────────────────────────────
def block_ip(ip: str, attempts: int, flog: logging.Logger, dry_run: bool) -> None:
    if ip in blocked_ips:
        log.info("SKIP     %-15s  already blocked", ip)
        return

    cmd = ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]

    if dry_run:
        log.info("DRY-RUN  %-15s  attempts=%d  would run: %s", ip, attempts, " ".join(cmd))
        blocked_ips.add(ip)
    else:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            blocked_ips.add(ip)
            log.info("BLOCKED  %-15s  attempts=%d", ip, attempts)
        except subprocess.CalledProcessError as exc:
            log.error("ERROR    %-15s  %s", ip, exc.stderr.strip())
            return   # don't write to blocker.log if iptables failed

    # Write block event to file — Promtail picks this up
    # Written in both normal and dry-run mode so the full Loki→Grafana
    # chain can be tested without needing root
    flog.info("BLOCKED  %-15s  attempts=%d", ip, attempts)


def record_failure(ip: str, flog: logging.Logger, dry_run: bool) -> None:
    now = time.time()

    # Prune attempts outside the sliding window
    fail_log[ip] = [t for t in fail_log[ip] if now - t < WINDOW]
    fail_log[ip].append(now)

    attempts = len(fail_log[ip])
    log.info("FAIL     %-15s  attempts=%d/%d", ip, attempts, THRESHOLD)

    if attempts >= THRESHOLD:
        block_ip(ip, attempts, flog, dry_run)


# ── Log tailer ─────────────────────────────────────────────────────────────────
def tail_log(flog: logging.Logger, dry_run: bool) -> None:
    log.info(
        "Watching %s  (threshold=%d, window=%ds)",
        AUTH_LOG, THRESHOLD, WINDOW,
    )
    try:
        with open(AUTH_LOG) as fh:
            fh.seek(0, 2)    # jump to EOF — only process new lines, not history
            while True:
                line = fh.readline()
                if not line:
                    time.sleep(0.25)
                    continue
                m = FAIL_PATTERN.search(line)
                if m:
                    record_failure(m.group(1), flog, dry_run)
    except FileNotFoundError:
        log.error("Auth log not found: %s", AUTH_LOG)
        raise


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="SSH brute-force auto-blocker")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print iptables commands without executing them (safe for testing)",
    )
    parser.add_argument("--threshold", type=int, default=THRESHOLD,
                        help=f"Failed attempts before block (default: {THRESHOLD})")
    parser.add_argument("--window", type=int, default=WINDOW,
                        help=f"Sliding window in seconds (default: {WINDOW})")
    parser.add_argument("--auth-log",    default=AUTH_LOG)
    parser.add_argument("--blocker-log", default=BLOCKER_LOG)
    args = parser.parse_args()

    global THRESHOLD, WINDOW, AUTH_LOG, BLOCKER_LOG
    THRESHOLD   = args.threshold
    WINDOW      = args.window
    AUTH_LOG    = args.auth_log
    BLOCKER_LOG = args.blocker_log

    if args.dry_run:
        log.info("DRY-RUN mode — iptables will NOT be executed")

    flog = setup_file_logger(BLOCKER_LOG)
    log.info("Block events → %s", BLOCKER_LOG)

    tail_log(flog, args.dry_run)


if __name__ == "__main__":
    main()
