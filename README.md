# EDU Q4 Weekly Report

Static site for the EDU initiative portfolio weekly report.

## Structure

```
index.html              — Single-file HTML report
data/roadmap.json       — Initiative data (regenerated weekly)
scripts/rebuild.py      — Google Sheets → JSON rebuild script
.github/workflows/      — GitHub Pages auto-deploy
```

## Weekly Update (Wednesdays)

1. Run the rebuild script to pull fresh data from Google Sheets:
   ```bash
   python3 scripts/rebuild.py --key path/to/service-account.json
   ```
2. Commit and push — GitHub Pages deploys automatically.

Or run manually via Claude in the weekly session, which generates `roadmap.json` directly from the Sheets connector.

## Setup

1. Create a new GitHub repo and push this folder
2. Enable GitHub Pages (Settings → Pages → Source: GitHub Actions)
3. For automated rebuilds, set up a Google Cloud service account with Sheets read access and add `GOOGLE_SERVICE_ACCOUNT_KEY` as a repository secret

## Data Source

Google Sheet: `14KsB_5McMVOZ6yn1wX5bRbSNQUyp81-2zwuusZX40Fg`
- **Roadmap tab** (12 cols): Initiative, Team, Business Owner, Phase, Status, milestones, Notes
- **Q4 Data tab** (31 cols): Full operational metadata including IDs, Slack channels, PRD links, actuals
