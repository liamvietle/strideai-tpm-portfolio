from __future__ import annotations

import csv
import hashlib
import io
import json
from xml.etree import ElementTree as ET

from app.models import ActivityRecord


def _text(element, path: str) -> str | None:
    found = element.find(path)
    return found.text.strip() if found is not None and found.text else None


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _seconds_from_duration(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return int(nums[0] * 3600 + nums[1] * 60 + nums[2])
    if len(nums) == 2:
        return int(nums[0] * 60 + nums[1])
    return None


def _stable_id(source: str, start_time: str, name: str | None) -> str:
    raw = f"{source}|{start_time}|{name or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def parse_tcx(content: str, *, athlete_id: str, source: str) -> list[ActivityRecord]:
    root = ET.fromstring(content)
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    records: list[ActivityRecord] = []

    for activity in root.findall(f".//{namespace}Activity"):
        activity_type = activity.attrib.get("Sport", "unknown").lower()
        start_time = _text(activity, f"{namespace}Id") or ""
        laps = activity.findall(f"{namespace}Lap")
        distance_m = 0.0
        duration_s = 0.0
        calories = 0.0
        hr_values: list[float] = []

        for lap in laps:
            distance_m += _float(_text(lap, f"{namespace}DistanceMeters")) or 0
            duration_s += _float(_text(lap, f"{namespace}TotalTimeSeconds")) or 0
            calories += _float(_text(lap, f"{namespace}Calories")) or 0
            for tp in lap.findall(f".//{namespace}Trackpoint"):
                hr = _float(_text(tp, f"{namespace}HeartRateBpm/{namespace}Value"))
                if hr is not None:
                    hr_values.append(hr)

        name = _text(activity, f"{namespace}Notes")
        source_id = _stable_id(source, start_time, name)
        records.append(ActivityRecord(
            source=source,
            source_activity_id=source_id,
            athlete_id=athlete_id,
            start_time=start_time,
            activity_type=activity_type,
            name=name,
            distance_km=round(distance_m / 1000, 3) if distance_m else None,
            duration_seconds=int(duration_s) if duration_s else None,
            average_hr=round(sum(hr_values) / len(hr_values), 1) if hr_values else None,
            max_hr=max(hr_values) if hr_values else None,
            calories=calories or None,
            raw_format="tcx",
            raw_payload=None,
        ))
    return records


GARMIN_ALIASES = {
    "activity_type": ("Activity Type", "ActivityType", "Type"),
    "date": ("Date", "Start Time", "StartTime", "Activity Date"),
    "name": ("Title", "Activity Name", "Name"),
    "distance": ("Distance", "Distance (km)", "Distance(km)"),
    "duration": ("Time", "Duration", "Elapsed Time"),
    "avg_hr": ("Avg HR", "Average HR", "Avg Heart Rate", "Average Heart Rate"),
    "max_hr": ("Max HR", "Max Heart Rate", "Maximum Heart Rate"),
    "calories": ("Calories",),
}


def _pick(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def parse_garmin_summary_csv(content: str, *, athlete_id: str) -> list[ActivityRecord]:
    reader = csv.DictReader(io.StringIO(content))
    records: list[ActivityRecord] = []
    for row in reader:
        start_time = _pick(row, GARMIN_ALIASES["date"]) or ""
        name = _pick(row, GARMIN_ALIASES["name"])
        records.append(ActivityRecord(
            source="garmin",
            source_activity_id=_stable_id("garmin", start_time, name),
            athlete_id=athlete_id,
            start_time=start_time,
            activity_type=(_pick(row, GARMIN_ALIASES["activity_type"]) or "unknown").lower(),
            name=name,
            distance_km=_float(_pick(row, GARMIN_ALIASES["distance"])),
            duration_seconds=_seconds_from_duration(_pick(row, GARMIN_ALIASES["duration"])),
            average_hr=_float(_pick(row, GARMIN_ALIASES["avg_hr"])),
            max_hr=_float(_pick(row, GARMIN_ALIASES["max_hr"])),
            calories=_float(_pick(row, GARMIN_ALIASES["calories"])),
            raw_format="garmin_summary_csv",
            raw_payload=json.dumps(row, separators=(",", ":")),
        ))
    return records
