#!/usr/bin/env python3
"""Capture Horse103 T-3 data and calculate the 60/40 Live103 + QP ranking.

Examples
  python horse103_t3.py --date 2026-09-13 --watch
  python horse103_t3.py --date 2026-09-13 --race 3 --capture-now

The script creates captures/<date>/ JSON evidence files and a summary CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


SUPABASE_URL = "https://pkrdkibqjwwgtvfdtwya.supabase.co"
PUBLIC_KEY = "sb_publishable_pP988ZhTMZ4GDYKk8AAnYw_kAViFMFI"
HK_TZ = timezone(timedelta(hours=8))
LIVE_WEIGHT = 0.60
QP_WEIGHT = 0.40


def ssl_context() -> ssl.SSLContext:
    """Use certifi when it is available (fixes common macOS Python CA installs)."""
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def request(path: str, body: dict | None = None) -> object:
    headers = {"apikey": os.getenv("HORSE103_PUBLIC_KEY", PUBLIC_KEY)}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(SUPABASE_URL + path, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_context()) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def rest(table: str, params: dict[str, str]) -> list[dict]:
    query = urllib.parse.urlencode(params, safe="(),*")
    result = request(f"/rest/v1/{table}?{query}")
    if not isinstance(result, list):
        raise RuntimeError(f"Unexpected {table} response")
    return result


def get_races(date: str) -> list[dict]:
    return rest("races", {
        "select": "id,race_number,post_time,venue,distance,course",
        "race_date": f"eq.{date}",
        "order": "race_number.asc",
    })


def get_base_race_id(date: str, forced: int | None) -> int:
    if forced is not None:
        return forced
    rows = rest("system_settings", {
        "select": "value",
        "key": "eq.ma288_current_race_day",
    })
    if not rows:
        raise RuntimeError("Cannot find the current race-day setting. Use --base-race-id.")
    value = rows[0].get("value")
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or value.get("race_date") != date:
        raise RuntimeError(
            "Horse103 has not set this as the current race day yet. "
            "Run this on race day, or pass --base-race-id after checking the setting."
        )
    return int(value["base_race_id"])


def get_tickets(date: str) -> list[dict]:
    """Read every ticket; the API serves pages of at most 1,000 rows."""
    all_rows: list[dict] = []
    last_id = 0
    while True:
        rows = rest("smart_money_tickets", {
            "select": "*",
            "race_date": f"eq.{date}",
            "id": f"gt.{last_id}",
            "order": "id.asc",
            "limit": "1000",
        })
        all_rows.extend(rows)
        if len(rows) < 1000:
            return all_rows
        last_id = int(rows[-1]["id"])


def get_entries(race_id: str) -> list[dict]:
    return rest("race_entries", {
        "select": "horse_number,horses(name_tc,name_en)",
        "race_id": f"eq.{race_id}",
        "is_standby": "eq.false",
        "withdrawn_at": "is.null",
    })


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def capture_race(
    race: dict,
    date: str,
    base_race_id: int,
    all_tickets: list[dict],
    live_override: dict | None = None,
) -> dict:
    live = live_override if live_override is not None else request("/functions/v1/live103-decision", {"raceId": race["id"]})
    if not isinstance(live, dict):
        raise RuntimeError("Unexpected Live103 response")
    lock_time = parse_utc(live["lockTime"])
    target_ticket_race_id = base_race_id + int(race["race_number"]) - 1

    qp_by_horse: defaultdict[int, float] = defaultdict(float)
    q_by_horse: defaultdict[int, float] = defaultdict(float)
    used_tickets: list[dict] = []
    for ticket in all_tickets:
        if int(ticket["race_id"]) != target_ticket_race_id:
            continue
        if parse_utc(ticket["scraped_at"]) > lock_time:
            continue
        bet_type = str(ticket["bet_type"]).upper()
        if bet_type not in {"Q", "QP"}:
            continue
        numbers = [int(n) for n in str(ticket["horse_or_combo"]).split("-") if n.isdigit()]
        if len(numbers) != 2:
            continue
        amount = float(ticket["amount"])
        destination = qp_by_horse if bet_type == "QP" else q_by_horse
        for number in set(numbers):
            destination[number] += amount
        used_tickets.append(ticket)

    candidates = {int(row["horseNumber"]): row for row in live.get("candidates", [])}
    entries = get_entries(race["id"])
    qp_max = max(qp_by_horse.values(), default=0.0)
    scores = []
    for entry in entries:
        number = int(entry["horse_number"])
        candidate = candidates.get(number, {})
        live_index = float(candidate.get("valueIndex") or 0)
        qp_amount = qp_by_horse[number]
        qp_strength = qp_amount / qp_max if qp_max else 0.0
        score = LIVE_WEIGHT * (live_index / 100.0) + QP_WEIGHT * qp_strength
        horse = entry.get("horses") or {}
        scores.append({
            "horse_number": number,
            "name_tc": horse.get("name_tc"),
            "name_en": horse.get("name_en"),
            "formula_score": round(score, 5),
            "live_value_index": live_index,
            "live_command": candidate.get("command"),
            "live_capital_signal": candidate.get("capitalSignal"),
            "is_live_candidate": number in candidates,
            "qp_amount": qp_amount,
            "q_amount": q_by_horse[number],
        })
    scores.sort(key=lambda row: (-row["formula_score"], -row["live_value_index"], row["horse_number"]))
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "formula": "S = 0.60 * (Live103 valueIndex / 100) + 0.40 * normalized QP amount",
        "race": race,
        "lock_time": live["lockTime"],
        "live103_raw": live,
        "ticket_cutoff": live["lockTime"],
        "base_race_id": base_race_id,
        "source_ticket_race_id": target_ticket_race_id,
        "qp_max_amount": qp_max,
        "used_q_and_qp_tickets": used_tickets,
        "ranking": scores,
        "main_pick": scores[0] if scores else None,
        "other_four": scores[1:5],
    }


def save_capture(capture: dict, output_root: Path) -> None:
    race = int(capture["race"]["race_number"])
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / f"race_{race:02d}_lock.json"
    json_path.write_text(json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = output_root / "summary.csv"
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "race", "lock_time", "rank", "horse_number", "name_tc", "formula_score",
            "live_value_index", "live_command", "qp_amount", "q_amount",
        ])
        if new_file:
            writer.writeheader()
        for rank, row in enumerate(capture["ranking"][:5], start=1):
            writer.writerow({
                "race": race,
                "lock_time": capture["lock_time"],
                "rank": rank,
                **{field: row.get(field) for field in writer.fieldnames if field not in {"race", "lock_time", "rank"}},
            })
    picks = [f"{row['horse_number']} {row['name_tc'] or ''}".strip() for row in capture["ranking"][:5]]
    print(f"Race {race}: main {picks[0] if picks else '—'} | other: {', '.join(picks[1:])}")
    print(f"Saved: {json_path}")


def hk_datetime(date: str, clock: str) -> datetime:
    return datetime.strptime(f"{date} {clock[:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=HK_TZ)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Horse103 T-3 ranking.")
    parser.add_argument("--date", required=True, help="Race date, YYYY-MM-DD")
    parser.add_argument("--watch", action="store_true", help="Wait and capture every race at T-3")
    parser.add_argument("--race", type=int, help="Capture only this race number")
    parser.add_argument("--capture-now", action="store_true", help="Capture immediately; useful for testing")
    parser.add_argument("--base-race-id", type=int, help="Override Horse103's current-day base race ID")
    parser.add_argument("--output", default="captures", help="Output folder")
    args = parser.parse_args()
    if not args.watch and not args.capture_now:
        parser.error("Choose --watch or --capture-now")

    races = get_races(args.date)
    if not races:
        raise RuntimeError(f"No Horse103 races found for {args.date}")
    if args.race:
        races = [race for race in races if int(race["race_number"]) == args.race]
        if not races:
            raise RuntimeError("That race number is not on this meeting")
    base_race_id = get_base_race_id(args.date, args.base_race_id)
    output_root = Path(args.output) / args.date

    for race in races:
        if args.watch:
            lock_at = hk_datetime(args.date, race["post_time"]) - timedelta(minutes=3)
            wait_seconds = (lock_at - datetime.now(HK_TZ)).total_seconds()
            if wait_seconds > 0:
                print(f"Race {race['race_number']}: waiting until {lock_at:%H:%M} Hong Kong time")
                time.sleep(wait_seconds)
            else:
                print(f"Race {race['race_number']}: lock time has passed; capturing current response")
        tickets = get_tickets(args.date)
        capture = capture_race(race, args.date, base_race_id, tickets)
        save_capture(capture, output_root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
