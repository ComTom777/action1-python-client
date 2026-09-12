"""Generates an org-wide compliance report combining Action1's native data
(patch/vulnerability compliance, endpoint status) with local CIS hardening
scan results (from the RmmServer Check-*.ps1 / Invoke-ComplianceScan.ps1
library, if you have a directory of its JSON output).

Why split this way: Action1 already tracks patch and vulnerability
compliance natively (see /updates and /vulnerabilities) - this script pulls
that from the API rather than re-detecting it locally. OS hardening posture
(password policy, firewall, BitLocker, RDP/SSH exposure, ...) is NOT tracked
by Action1, so that side comes from local scan JSON if you provide it.

Usage:
    export ACTION1_CLIENT_ID=api-key-xxx@action1.com
    export ACTION1_CLIENT_SECRET=...
    export ACTION1_REGION=europe   # optional, default north_america

    python generate_compliance_report.py --org-id <org-id> --out ./report \
        [--scans-dir /path/to/collected/Invoke-ComplianceScan/json/files]

Output (written into --out, created if missing):
    endpoints.csv           - one row per endpoint: status, OS, patch/vuln
                               status, and (if matched) CIS compliance %
    vulnerabilities.csv     - every CVE affecting the org, sorted by risk
    missing_updates.csv     - every missing update, sorted by severity/SLA
    summary.html            - one-page overview with the top risks
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from action1_client import Action1Client  # noqa: E402

# Rank low->high so "worst wins" comparisons are a single max()/sort key.
_SEVERITY_RANK = {"low": 0, "moderate": 1, "medium": 1, "important": 2, "high": 2, "critical": 3}
_SLA_RANK = {"due later": 0, "due soon": 1, "overdue": 2}

# Action1's endpoint last_seen format, e.g. "2026-01-14_17-25-29".
_ACTION1_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


def days_since(timestamp: str | None) -> int | None:
    """Days between an Action1 'last_seen'-style timestamp and now, or None if unparseable."""
    if not timestamp:
        return None
    try:
        then = datetime.strptime(timestamp, _ACTION1_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - then).days


def _severity_rank(value: str | None) -> int:
    return _SEVERITY_RANK.get((value or "").strip().lower(), -1)


def _sla_rank(value: str | None) -> int:
    return _SLA_RANK.get((value or "").strip().lower(), -1)


def load_local_scans(scans_dir: str | None) -> dict[str, dict]:
    """Loads Invoke-ComplianceScan.ps1 JSON output files, keyed by lowercased hostname."""
    scans: dict[str, dict] = {}
    if not scans_dir:
        return scans
    for path in Path(scans_dir).glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"warning: could not read {path}: {exc}", file=sys.stderr)
            continue
        hostname = data.get("Hostname")
        if hostname:
            scans[hostname.lower()] = data
    return scans


def build_endpoints_rows(
    endpoints: list[dict], scans: dict[str, dict], stale_days: int = 30
) -> list[dict]:
    """Builds one row per endpoint, flagging data as stale by *Action1's own* last_seen -
    not by our CIS scan's self-reported timestamp, which only records when the check last
    happened to run and says nothing about whether the endpoint is still reachable now. An
    endpoint disconnected for a year has a last_seen from a year ago; that's the signal that
    makes its compliance numbers (ours or Action1's) not worth trusting, regardless of what
    the scan script itself stamped.
    """
    rows = []
    for ep in endpoints:
        scan = scans.get((ep.get("name") or "").lower())
        summary = scan.get("Summary", {}) if scan else {}
        last_seen_days = days_since(ep.get("last_seen"))
        rows.append(
            {
                "name": ep.get("name"),
                "platform": ep.get("platform"),
                "os": ep.get("OS"),
                "status": ep.get("status"),
                "last_seen": ep.get("last_seen"),
                "days_since_last_seen": last_seen_days if last_seen_days is not None else "",
                "stale": (
                    ep.get("status") != "Connected"
                    and last_seen_days is not None
                    and last_seen_days > stale_days
                ),
                "reboot_required": ep.get("reboot_required"),
                "update_status": ep.get("update_status"),
                "vulnerability_status": ep.get("vulnerability_status"),
                "groups": "; ".join(g.get("name", "") for g in ep.get("group_membership", [])),
                "cis_compliance_percent": summary.get("CompliancePercent", ""),
                "cis_failed_checks": summary.get("Failed", ""),
                "cis_scan_timestamp": scan.get("ScanTimestamp", "") if scan else "",
            }
        )
    return rows


def build_vulnerabilities_rows(vulnerabilities: list[dict]) -> list[dict]:
    rows = []
    for v in vulnerabilities:
        rows.append(
            {
                "cve_id": v.get("cve_id"),
                "cvss_score": v.get("cvss_score"),
                "cisa_kev": v.get("cisa_kev"),
                "endpoints_count": v.get("endpoints_count"),
                "remediation_status": v.get("remediation_status"),
                "remediation_deadline": v.get("remediation_deadline"),
                "affected_software": "; ".join(
                    s.get("product_name", "") for s in v.get("software", [])
                ),
            }
        )
    # CISA Known Exploited Vulnerabilities first (actively exploited in the wild), then by CVSS.
    rows.sort(
        key=lambda r: (r["cisa_kev"] == "Yes", float(r["cvss_score"] or 0)),
        reverse=True,
    )
    return rows


def build_missing_updates_rows(updates: list[dict]) -> list[dict]:
    rows = []
    for pkg in updates:
        versions = pkg.get("versions", [])
        worst_severity = max(versions, key=lambda v: _severity_rank(v.get("security_severity")), default={})
        worst_sla = max(versions, key=lambda v: _sla_rank(v.get("update_sla_status")), default={})
        rows.append(
            {
                "name": pkg.get("name"),
                "vendor": pkg.get("vendor"),
                "platform": pkg.get("platform"),
                "update_type": pkg.get("update_type"),
                "worst_severity": worst_severity.get("security_severity", ""),
                "worst_sla_status": worst_sla.get("update_sla_status", ""),
                "sla_deadline": worst_sla.get("update_sla_deadline", ""),
                "version_count": len(versions),
            }
        )
    rows.sort(
        key=lambda r: (_sla_rank(r["worst_sla_status"]), _severity_rank(r["worst_severity"])),
        reverse=True,
    )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _html_table(rows: list[dict], columns: list[str], limit: int = 15) -> str:
    if not rows:
        return "<p><em>None.</em></p>"
    head = "".join(f"<th>{c}</th>" for c in columns)
    body_rows = []
    for r in rows[:limit]:
        cells = "".join(f"<td>{r.get(c, '')}</td>" for c in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def write_summary_html(
    path: Path,
    org: dict,
    endpoint_rows: list[dict],
    vuln_rows: list[dict],
    update_rows: list[dict],
    has_scan_data: bool,
    stale_days: int = 30,
) -> None:
    total = len(endpoint_rows)
    connected = sum(1 for r in endpoint_rows if r["status"] == "Connected")
    stale_rows = [r for r in endpoint_rows if r["stale"]]
    reboot_pending = sum(1 for r in endpoint_rows if r["reboot_required"] == "Yes")
    kev_count = sum(1 for r in vuln_rows if r["cisa_kev"] == "Yes")
    overdue_updates = sum(1 for r in update_rows if r["worst_sla_status"] == "Overdue")

    # Excludes stale endpoints: a compliance % from a host not seen in months isn't "current"
    # posture, and averaging it in would understate/overstate the fleet's real state.
    cis_scores = [
        float(r["cis_compliance_percent"])
        for r in endpoint_rows
        if r["cis_compliance_percent"] not in ("", None) and not r["stale"]
    ]
    avg_cis = f"{sum(cis_scores) / len(cis_scores):.1f}%" if cis_scores else "no scan data"

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Compliance Report - {org.get('name', '')}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f2f2f2; }}
  .stat-row {{ display: flex; gap: 2rem; flex-wrap: wrap; margin: 1rem 0; }}
  .stat {{ background: #f7f7f7; border-radius: 8px; padding: 0.75rem 1.25rem; }}
  .stat .n {{ font-size: 1.6rem; font-weight: 600; display: block; }}
  .stat .l {{ font-size: 0.8rem; color: #555; }}
</style></head>
<body>
<h1>Compliance Report - {org.get('name', org.get('id', ''))}</h1>
<div class="stat-row">
  <div class="stat"><span class="n">{total}</span><span class="l">Endpoints</span></div>
  <div class="stat"><span class="n">{connected}</span><span class="l">Connected</span></div>
  <div class="stat"><span class="n">{len(stale_rows)}</span><span class="l">Stale (not seen &gt;{stale_days}d)</span></div>
  <div class="stat"><span class="n">{reboot_pending}</span><span class="l">Reboot pending</span></div>
  <div class="stat"><span class="n">{len(vuln_rows)}</span><span class="l">Open CVEs</span></div>
  <div class="stat"><span class="n">{kev_count}</span><span class="l">CISA KEV (actively exploited)</span></div>
  <div class="stat"><span class="n">{overdue_updates}</span><span class="l">Overdue updates</span></div>
  <div class="stat"><span class="n">{avg_cis}</span><span class="l">Avg CIS hardening score (excl. stale)</span></div>
</div>

<h2>Top vulnerabilities (CISA KEV first, then by CVSS)</h2>
{_html_table(vuln_rows, ["cve_id", "cvss_score", "cisa_kev", "endpoints_count", "remediation_status", "affected_software"])}

<h2>Top missing updates (overdue / severe first)</h2>
{_html_table(update_rows, ["name", "vendor", "worst_severity", "worst_sla_status", "sla_deadline", "version_count"])}

<h2>Stale endpoints (data below is not current)</h2>
<p>Not connected and not seen in over {stale_days} days - any compliance/patch/vulnerability
data shown for these is a snapshot from whenever they were last online, not their current state.</p>
{_html_table(stale_rows, ["name", "status", "days_since_last_seen", "cis_compliance_percent"], limit=50)}

<h2>Endpoints{"" if has_scan_data else " (no local CIS scan data supplied - run with --scans-dir)"}</h2>
{_html_table(endpoint_rows, ["name", "os", "status", "days_since_last_seen", "stale", "reboot_required", "update_status", "vulnerability_status", "cis_compliance_percent"], limit=50)}

</body></html>
"""
    path.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--org-id", help="Organization ID. Defaults to the first org visible to the credentials.")
    parser.add_argument("--out", default="./report", help="Output directory (default: ./report)")
    parser.add_argument("--scans-dir", help="Directory of Invoke-ComplianceScan.ps1 JSON output, one file per host")
    parser.add_argument(
        "--stale-days", type=int, default=30,
        help="Flag endpoints not seen in this many days (and not Connected) as stale (default: 30)",
    )
    args = parser.parse_args()

    client_id = os.environ["ACTION1_CLIENT_ID"]
    client_secret = os.environ["ACTION1_CLIENT_SECRET"]
    region = os.environ.get("ACTION1_REGION", "north_america")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Action1Client(client_id, client_secret, region=region) as client:
        org_id = args.org_id
        if not org_id:
            orgs = client.list_organizations()
            if not orgs:
                sys.exit("No organizations visible to these credentials.")
            org_id = orgs[0]["id"]
        org = client.get_organization(org_id)

        endpoints = client.list_endpoints(org_id)
        vulnerabilities = client.list_vulnerabilities(org_id)
        missing_updates = client.list_missing_updates(org_id)

    scans = load_local_scans(args.scans_dir)
    endpoint_rows = build_endpoints_rows(endpoints, scans, stale_days=args.stale_days)
    vuln_rows = build_vulnerabilities_rows(vulnerabilities)
    update_rows = build_missing_updates_rows(missing_updates)

    write_csv(out_dir / "endpoints.csv", endpoint_rows)
    write_csv(out_dir / "vulnerabilities.csv", vuln_rows)
    write_csv(out_dir / "missing_updates.csv", update_rows)
    write_summary_html(
        out_dir / "summary.html", org, endpoint_rows, vuln_rows, update_rows, bool(scans),
        stale_days=args.stale_days,
    )

    print(f"Report written to {out_dir.resolve()}")
    print(f"  {len(endpoint_rows)} endpoints, {len(vuln_rows)} vulnerabilities, {len(update_rows)} missing updates")
    if args.scans_dir and not scans:
        print(f"  warning: no scan JSON files matched in {args.scans_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
