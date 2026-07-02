#!/usr/bin/env python3
"""CLI helper for the Plasma widget: read status, edit anchors, live-preview brightness.

Shells out from QML via Plasma5Support's executable DataSource, since plain QML
has no built-in JSON file I/O or D-Bus bindings.
"""

import argparse
import json
import sys
from datetime import datetime

import dbus

import schedcore


def cmd_get_status(_args) -> None:
    config = schedcore.load_config()
    loc_cfg = config["location"]
    today = datetime.now().astimezone().date()
    times = schedcore.sun_times_for(loc_cfg, today)

    out = {
        "enabled": config.get("enabled", True),
        "times": {k: v.strftime("%H:%M") for k, v in times.items()},
        "monitors": {
            key: {"label": mon["label"], "anchors": mon["anchors"]}
            for key, mon in config["monitors"].items()
        },
    }
    print(json.dumps(out))


def cmd_set_anchor(args) -> None:
    if args.anchor not in schedcore.ANCHOR_ORDER:
        sys.exit(f"unknown anchor: {args.anchor}")
    config = schedcore.load_config()
    if args.monitor not in config["monitors"]:
        sys.exit(f"unknown monitor: {args.monitor}")
    config["monitors"][args.monitor]["anchors"][args.anchor] = max(0, min(100, args.value))
    schedcore.save_config(config)


def cmd_set_enabled(args) -> None:
    config = schedcore.load_config()
    config["enabled"] = args.value
    schedcore.save_config(config)


def cmd_preview(args) -> None:
    config = schedcore.load_config()
    if args.monitor not in config["monitors"]:
        sys.exit(f"unknown monitor: {args.monitor}")
    dbus_path = config["monitors"][args.monitor]["dbus_path"]
    bus = dbus.SessionBus()
    schedcore.set_brightness(bus, dbus_path, args.value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("get-status", help="print current config + today's sun times as JSON").set_defaults(func=cmd_get_status)

    p = sub.add_parser("set-anchor", help="update a brightness anchor point")
    p.add_argument("monitor")
    p.add_argument("anchor", choices=schedcore.ANCHOR_ORDER)
    p.add_argument("value", type=int)
    p.set_defaults(func=cmd_set_anchor)

    p = sub.add_parser("set-enabled", help="toggle the whole automation on/off")
    p.add_argument("value", type=lambda s: s.lower() in ("1", "true", "on", "yes"))
    p.set_defaults(func=cmd_set_enabled)

    p = sub.add_parser("preview", help="live-set a monitor's brightness without persisting it")
    p.add_argument("monitor")
    p.add_argument("value", type=float)
    p.set_defaults(func=cmd_preview)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
