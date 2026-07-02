#!/usr/bin/env python3
"""Set external-monitor brightness from a sun-relative schedule via Plasma's D-Bus API.

Invoked periodically by the brightness-scheduler.timer systemd unit.
"""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import dbus

import schedcore

CACHE_PATH = Path(
    os.environ.get("XDG_CACHE_HOME", "~/.cache")
).expanduser() / "brightness-scheduler" / "last.json"

TOLERANCE = 100  # 1% of MAX_BRIGHTNESS, avoids needless DDC writes to the flaky Acer link

log = logging.getLogger("brightness-scheduler")


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run a single pass and exit (default behavior)")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--dry-run", action="store_true", help="compute but do not call D-Bus")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config = schedcore.load_config()
    if not config.get("enabled", True):
        log.info("automation disabled in config, skipping")
        return

    loc_cfg = config["location"]
    now = datetime.now().astimezone()
    cache = load_cache()

    bus = None if args.dry_run else dbus.SessionBus()

    for key, mon_cfg in config["monitors"].items():
        points = schedcore.build_anchor_points(mon_cfg["anchors"], loc_cfg, now)
        target_pct = schedcore.interpolate(points, now)
        target_raw = int(round(target_pct / 100 * schedcore.MAX_BRIGHTNESS))
        last_raw = cache.get(key)

        log.debug("%s: target=%.1f%% last=%s", key, target_pct, last_raw)

        if last_raw is not None and abs(target_raw - last_raw) < TOLERANCE:
            log.debug("%s: within tolerance, skipping", key)
            continue

        if args.dry_run:
            log.info("[dry-run] would set %s -> %.1f%%", key, target_pct)
        else:
            schedcore.set_brightness(bus, mon_cfg["dbus_path"], target_pct)
            log.info("set %s (%s) -> %.0f%%", key, mon_cfg["dbus_path"], target_pct)

        cache[key] = target_raw

    if not args.dry_run:
        save_cache(cache)


if __name__ == "__main__":
    main()
