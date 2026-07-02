"""Shared config/D-Bus/sun-math helpers for brightness-scheduler.py and schedctl.py."""

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import dbus
from astral import LocationInfo
from astral.sun import sun

CONFIG_PATH = Path(
    os.environ.get("XDG_CONFIG_HOME", "~/.config")
).expanduser() / "brightness-scheduler" / "config.json"

DBUS_SERVICE = "org.kde.org_kde_powerdevil"
DBUS_INTERFACE = "org.kde.ScreenBrightness.Display"
MAX_BRIGHTNESS = 10000
ANCHOR_ORDER = ("night", "sunrise", "noon", "sunset")

# org.kde.ScreenBrightness.Display SetBrightness flags (powerdevilscreenbrightnessagent.h)
SUPPRESS_INDICATOR = 0x1


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=CONFIG_PATH.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, CONFIG_PATH)
    except BaseException:
        os.unlink(tmp_path)
        raise


def sun_times_for(loc_cfg: dict, day: date) -> dict:
    """Return {'sunrise': dt, 'noon': dt, 'sunset': dt} in local tz for the given day."""
    location = LocationInfo(
        name=loc_cfg["name"],
        region=loc_cfg["region"],
        timezone=loc_cfg["timezone"],
        latitude=loc_cfg["latitude"],
        longitude=loc_cfg["longitude"],
    )
    s = sun(location.observer, date=day, tzinfo=location.timezone)
    return {"sunrise": s["sunrise"], "noon": s["noon"], "sunset": s["sunset"]}


def build_anchor_points(anchors: dict, loc_cfg: dict, now: datetime) -> list[tuple[datetime, float]]:
    """Sorted (datetime, brightness_pct) points spanning yesterday..tomorrow midnight,
    so `now` always falls between two consecutive points (midnight-wrap-safe interpolation)."""
    tz = now.tzinfo
    points: list[tuple[datetime, float]] = []
    for day_offset in (-1, 0, 1):
        day = now.date() + timedelta(days=day_offset)
        midnight = datetime.combine(day, datetime.min.time(), tzinfo=tz)
        points.append((midnight, anchors["night"]))
        times = sun_times_for(loc_cfg, day)
        points.append((times["sunrise"], anchors["sunrise"]))
        points.append((times["noon"], anchors["noon"]))
        points.append((times["sunset"], anchors["sunset"]))
    points.sort(key=lambda p: p[0])
    return points


def interpolate(points: list[tuple[datetime, float]], now: datetime) -> float:
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= now <= t1:
            if t1 == t0:
                return v0
            frac = (now - t0).total_seconds() / (t1 - t0).total_seconds()
            return v0 + (v1 - v0) * frac
    return points[0][1]


def set_brightness(bus: "dbus.SessionBus", dbus_path: str, pct: float) -> int:
    obj = bus.get_object(DBUS_SERVICE, dbus_path)
    iface = dbus.Interface(obj, DBUS_INTERFACE)
    value = int(round(pct / 100 * MAX_BRIGHTNESS))
    iface.SetBrightness(dbus.Int32(value), dbus.UInt32(SUPPRESS_INDICATOR))
    return value
