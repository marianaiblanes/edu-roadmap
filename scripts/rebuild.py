#!/usr/bin/env python3
"""
rebuild.py — Pull EDU Q4 Roadmap data from Google Sheets and write data/roadmap.json.

Usage:
  python3 scripts/rebuild.py                     # uses GOOGLE_SERVICE_ACCOUNT_KEY env var
  python3 scripts/rebuild.py --key creds.json    # uses service account JSON file

Requirements:
  pip install google-auth google-auth-httplib2 google-api-python-client

The script reads two tabs from the Q4 Roadmap spreadsheet:
  - "Roadmap" (A:L) — 12-column clean view
  - "Q4 Data" (A:AE) — 31-column operational detail

It merges them by initiative name and writes data/roadmap.json.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SPREADSHEET_ID = "14KsB_5McMVOZ6yn1wX5bRbSNQUyp81-2zwuusZX40Fg"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Slack ID lookups
OWNER_SLACK = {
    "Ana Sofía Acuña González": "U07G4N0523D",
    "Norimar Gayoso Sifre": "U03TVLG5YJX",
    "Alani Lay Fumero": "U097XS4BQJV",
    "Alondra Mendoza": "U097FCW6M3Q",
    "Luly Porro-Cabrera": "U07PJG74H18",
    "Natalia Fernandez": "U077DT43FME",
    "Isabel Mirandés Suárez": "U05HUP14P6C",
    "Owen Heath": "U6HPQFQLU",
    "Camila Sadurni": "U05H7FEPA4U",
    "Jessy Epley": "U010TS5000P",
    "Carlos Covas": "U023GUWNM54",
    "Julian Silva": "U05GQFUN8ET",
    "Marie Custodio Collazo": "U0740RN4S4T",
    "Alex Agosto": "U075GG9PMNW",
    "Anthony Rossomano": "U0B2TRF08",
    "Joaquín Nieves": "U05GYCC347Q",
    "Gabriela Arroyo": "U079H4JST4J",
}

LEAD_SLACK = {
    "Kidany Figueroa": "U092UF27DT6",
    "Joe Rodriguez": "U08NS5RST6U",
    "Jason Sosa Pagan": "U0AMT9CSREH",
    "Eduardo Pérez Cortés": "U0AA2HUF6QJ",
    "Rogelio Vazquez-Rivera": "U089X3AMRT6",
    "Johan Rivera": "U014S4GFPU7",
}


def get_sheets_service(key_path=None):
    """Authenticate and return a Sheets API service."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if key_path:
        creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    elif os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY"):
        import json as _json, io
        info = _json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"])
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        print("ERROR: No credentials. Set GOOGLE_SERVICE_ACCOUNT_KEY or pass --key.", file=sys.stderr)
        sys.exit(1)

    return build("sheets", "v4", credentials=creds)


def fetch_tab(service, tab_range):
    """Fetch a tab's values."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=tab_range
    ).execute()
    return result.get("values", [])


def build_json(roadmap_rows, q4_data_rows):
    """Transform raw sheet rows into the roadmap.json structure."""
    # Parse headers
    rm_header = roadmap_rows[0]
    q4_header = q4_data_rows[0]

    # Build Q4 Data lookup by initiative name (column A)
    q4_lookup = {}
    for row in q4_data_rows[1:]:
        if len(row) < 2:
            continue
        padded = row + [""] * (len(q4_header) - len(row))
        entry = dict(zip(q4_header, padded))
        q4_lookup[entry["Initiative"]] = entry

    initiatives = []
    for row in roadmap_rows[1:]:
        if len(row) < 12:
            row = row + [""] * (12 - len(row))
        name, team, biz_owner, phase, status = row[0:5]
        creative_done, handoff, tech_start, tech_end, uat_done, launch, notes = row[5:12]

        # Match to Q4 Data
        detail = q4_lookup.get(name, {})

        eng_lead = detail.get("Engineering Lead", "")
        biz_slack = None
        for part in biz_owner.split(" / "):
            part = part.strip()
            if part in OWNER_SLACK:
                biz_slack = OWNER_SLACK[part]
                break

        init = {
            "id": detail.get("Initiative ID", ""),
            "name": name,
            "team": team,
            "bizOwner": biz_owner,
            "engLead": eng_lead,
            "epic": detail.get("RVEDU Epic", ""),
            "slackChannel": detail.get("Slack Channel ID", ""),
            "prd": detail.get("PRD Link", ""),
            "phase": phase,
            "status": status,
            "milestones": {
                "creativeDone": creative_done,
                "handoffToTech": handoff,
                "techStart": tech_start,
                "techEnd": tech_end,
                "uatDone": uat_done,
                "launch": launch,
            },
            "notes": notes,
            "bizOwnerSlackId": biz_slack,
            "engLeadSlackId": LEAD_SLACK.get(eng_lead),
            "autoInterpreted": False,
            "lastUpdated": detail.get("Last Updated", datetime.now().strftime("%Y-%m-%d")),
        }
        initiatives.append(init)

    # Summary
    by_status, by_phase, by_team = {}, {}, {}
    active, launched, pushed = 0, 0, 0
    for i in initiatives:
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1
        by_phase[i["phase"]] = by_phase.get(i["phase"], 0) + 1
        t = i["team"]
        if t not in by_team:
            by_team[t] = {"total": 0, "active": 0, "pushed": 0, "launched": 0}
        by_team[t]["total"] += 1

        if i["phase"] == "LAUNCHED":
            launched += 1
            by_team[t]["launched"] += 1
        elif "Not Q4 required" in i["notes"] or ("Pushed to" in i["notes"] and "2027" in i["notes"]):
            pushed += 1
            by_team[t]["pushed"] += 1
        else:
            active += 1
            by_team[t]["active"] += 1

    today = datetime.now().strftime("%Y-%m-%d")
    monday = datetime.now()
    # Find Monday of current week
    monday_offset = monday.weekday()  # 0=Mon
    from datetime import timedelta
    monday = monday - timedelta(days=monday_offset)

    return {
        "meta": {
            "generated": datetime.now().isoformat(),
            "source": f"Google Sheet {SPREADSHEET_ID}",
            "weekOf": today,
            "reportWeek": f"Week of {monday.strftime('%b %d, %Y')}",
            "codeFreeze": {"start": "2026-12-16", "end": "2027-01-05"},
            "companyShutdown": {"start": "2026-12-25", "end": "2026-12-31"},
            "holidays": {"thanksgiving": ["2026-11-26", "2026-11-27"]},
        },
        "teams": sorted(set(i["team"] for i in initiatives), key=lambda t: ["Charlotte","edX","HEN","Affiliates","Partnerships","Product"].index(t) if t in ["Charlotte","edX","HEN","Affiliates","Partnerships","Product"] else 99),
        "initiatives": initiatives,
        "summary": {
            "total": len(initiatives),
            "activeThisQuarter": active,
            "launched": launched,
            "pushedTo2027": pushed,
            "byStatus": by_status,
            "byPhase": by_phase,
            "byTeam": by_team,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Rebuild roadmap.json from Google Sheets")
    parser.add_argument("--key", help="Path to service account JSON key file")
    parser.add_argument("--output", default="data/roadmap.json", help="Output path (default: data/roadmap.json)")
    args = parser.parse_args()

    service = get_sheets_service(args.key)

    print("Fetching Roadmap tab...")
    roadmap = fetch_tab(service, "Roadmap!A1:L50")
    print(f"  → {len(roadmap)-1} rows")

    print("Fetching Q4 Data tab...")
    q4_data = fetch_tab(service, "'Q4 Data'!A1:AE50")
    print(f"  → {len(q4_data)-1} rows")

    result = build_json(roadmap, q4_data)
    
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nWritten {result['summary']['total']} initiatives to {out_path}")
    print(f"  Active: {result['summary']['activeThisQuarter']} | Launched: {result['summary']['launched']} | Pushed: {result['summary']['pushedTo2027']}")


if __name__ == "__main__":
    main()
