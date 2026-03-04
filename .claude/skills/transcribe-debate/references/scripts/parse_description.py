#!/usr/bin/env python3
"""
Parse a BP debate YouTube video description into structured metadata.

Usage:
    python parse_description.py <youtube_url>
    python parse_description.py <youtube_url> --json

Outputs structured debate metadata: motion, teams, speakers, panel, results.
"""

import subprocess
import json
import re
import sys


def fetch_metadata(url: str) -> dict:
    """Fetch title, description, upload_date from yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "--skip-download", "--print", "%(.{title,description,upload_date})j", url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")
    return json.loads(result.stdout.strip())


def parse_description(description: str) -> dict:
    """Parse the debate description into structured data."""
    lines = description.strip().split("\n")
    meta = {
        "disclaimer": None,
        "info_slide": None,
        "motion": None,
        "teams": {},
        "panel": [],
        "chair": None,
        "results": None,
    }

    # Extract disclaimer (usually first line, wrapped in **)
    for line in lines:
        stripped = line.strip().strip("*")
        if "שובצו אקראית" in stripped or "אינם בהכרח" in stripped:
            meta["disclaimer"] = stripped
            break

    # Extract info slide (lines after "שקופית מידע:")
    info_start = None
    for i, line in enumerate(lines):
        if "שקופית מידע" in line:
            info_start = i
            break
    if info_start is not None:
        info_lines = []
        for line in lines[info_start + 1:]:
            if line.strip() == "" or ":" in line and any(k in line for k in ["מושן", "ממ1", "אופ1", "ממ2", "אופ2", "פאנל", "מיקומים"]):
                break
            info_lines.append(line.strip())
        meta["info_slide"] = " ".join(info_lines).strip()

    # Extract motion
    for line in lines:
        if "מושן:" in line or "מוושן:" in line:
            meta["motion"] = line.split(":", 1)[1].strip()
            break

    # Extract teams — pattern: "ממ1:", "אופ1:", "ממ2:", "אופ2:"
    team_map = {
        "ממ1": "OG",
        "אופ1": "OO",
        "ממ2": "CG",
        "אופ2": "CO",
    }

    for line in lines:
        for prefix, team_code in team_map.items():
            if line.strip().startswith(prefix + ":"):
                names_str = line.split(":", 1)[1].strip()
                names = [n.strip() for n in names_str.split(",") if n.strip()]
                meta["teams"][team_code] = names

    # Extract panel
    panel_started = False
    for line in lines:
        if "פאנל" in line and ":" in line:
            # Panel names might be on the same line after ":"
            after_colon = line.split(":", 1)[1].strip()
            if after_colon:
                meta["panel"] = [n.strip() for n in after_colon.split(",") if n.strip()]
            panel_started = True
            continue
        if panel_started and line.strip():
            # Panel names on the next line
            if any(k in line for k in ["מיקומים", "מושן"]):
                panel_started = False
                continue
            names = [n.strip() for n in line.split(",") if n.strip()]
            meta["panel"].extend(names)
            panel_started = False

    # Extract chair (marked with Ⓒ)
    for name in meta["panel"]:
        if "Ⓒ" in name or "©" in name:
            meta["chair"] = name.replace("Ⓒ", "").replace("©", "").strip()

    # Clean Ⓒ from panel list
    meta["panel"] = [n.replace("Ⓒ", "").replace("©", "").strip() for n in meta["panel"]]

    # Extract results
    for line in lines:
        if "מנצחים" in line or "מנצחות" in line:
            meta["results"] = line.strip()
            break

    return meta


def speakers_by_speech(teams: dict) -> list:
    """Map team members to BP speech positions."""
    # In BP, each team has 2 speakers in order
    # OG: PM, DPM — OO: LO, DLO — CG: MG, GW — CO: MO, OW
    speech_roles = [
        ("PM", "ראש ממשלה", "OG", 0),
        ("LO", "ראש אופוזיציה", "OO", 0),
        ("DPM", "סגנ/ית ראש ממשלה", "OG", 1),
        ("DLO", "סגנ/ית ראש אופוזיציה", "OO", 1),
        ("MG", "חבר/ת ממשלה", "CG", 0),
        ("MO", "חבר/ת אופוזיציה", "CO", 0),
        ("GW", "שוט ממשלה", "CG", 1),
        ("OW", "שוט אופוזיציה", "CO", 1),
    ]

    result = []
    for abbr, role_he, team_code, idx in speech_roles:
        names = teams.get(team_code, [])
        speaker_name = names[idx] if idx < len(names) else "?"
        result.append({
            "speech_num": len(result) + 1,
            "abbr": abbr,
            "role_he": role_he,
            "team_code": team_code,
            "speaker_name": speaker_name,
        })
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_description.py <youtube_url> [--json]")
        sys.exit(1)

    url = sys.argv[1]
    as_json = "--json" in sys.argv

    raw = fetch_metadata(url)
    meta = parse_description(raw["description"])
    meta["title"] = raw["title"]
    meta["upload_date"] = raw["upload_date"]
    meta["url"] = url
    meta["speakers"] = speakers_by_speech(meta["teams"])

    if as_json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        print(f"כותרת: {meta['title']}")
        print(f"תאריך: {meta['upload_date']}")
        print(f"מושן: {meta['motion']}")
        print()
        print("דוברים:")
        for s in meta["speakers"]:
            print(f"  נאום {s['speech_num']}: {s['speaker_name']} — {s['role_he']} ({s['abbr']}, {s['team_code']})")
        print()
        if meta["panel"]:
            chair_mark = lambda n: f"{n} (יו\"ר)" if n == meta.get("chair") else n
            print(f"פאנל: {', '.join(chair_mark(n) for n in meta['panel'])}")
        if meta["results"]:
            print(f"תוצאות: {meta['results']}")
        if meta["disclaimer"]:
            print(f"\n⚠ {meta['disclaimer']}")


if __name__ == "__main__":
    main()
