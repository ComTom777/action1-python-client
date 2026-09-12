import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reports"))

from generate_compliance_report import (  # noqa: E402
    build_endpoints_rows,
    build_missing_updates_rows,
    build_vulnerabilities_rows,
    days_since,
    load_local_scans,
)


def _timestamp_days_ago(days: int) -> str:
    then = datetime.now(timezone.utc) - timedelta(days=days)
    return then.strftime("%Y-%m-%d_%H-%M-%S")


def test_vulnerabilities_sorted_kev_first_then_cvss():
    vulns = [
        {"cve_id": "low-cvss", "cvss_score": "3.0", "cisa_kev": "No", "endpoints_count": "1"},
        {"cve_id": "kev-but-lower-cvss", "cvss_score": "5.0", "cisa_kev": "Yes", "endpoints_count": "1"},
        {"cve_id": "high-cvss-no-kev", "cvss_score": "9.8", "cisa_kev": "No", "endpoints_count": "1"},
    ]
    rows = build_vulnerabilities_rows(vulns)
    assert [r["cve_id"] for r in rows] == ["kev-but-lower-cvss", "high-cvss-no-kev", "low-cvss"]


def test_vulnerabilities_joins_affected_software_names():
    vulns = [
        {
            "cve_id": "CVE-1",
            "cvss_score": "7.0",
            "cisa_kev": "No",
            "software": [{"product_name": "Chrome"}, {"product_name": "Edge"}],
        }
    ]
    rows = build_vulnerabilities_rows(vulns)
    assert rows[0]["affected_software"] == "Chrome; Edge"


def test_missing_updates_sorted_overdue_and_severity_first():
    updates = [
        {"name": "due-later-critical", "versions": [{"update_sla_status": "Due later", "security_severity": "Critical"}]},
        {"name": "overdue-unspecified", "versions": [{"update_sla_status": "Overdue", "security_severity": "Unspecified"}]},
        {"name": "overdue-critical", "versions": [{"update_sla_status": "Overdue", "security_severity": "Critical"}]},
    ]
    rows = build_missing_updates_rows(updates)
    assert [r["name"] for r in rows] == ["overdue-critical", "overdue-unspecified", "due-later-critical"]


def test_missing_updates_handles_package_with_no_versions():
    rows = build_missing_updates_rows([{"name": "no-versions", "versions": []}])
    assert rows[0]["worst_severity"] == ""
    assert rows[0]["worst_sla_status"] == ""
    assert rows[0]["version_count"] == 0


def test_load_local_scans_keys_by_lowercased_hostname(tmp_path):
    scan_file = tmp_path / "host1.json"
    scan_file.write_text(json.dumps({"Hostname": "Host1", "Summary": {"CompliancePercent": 80}}))

    scans = load_local_scans(str(tmp_path))

    assert "host1" in scans
    assert scans["host1"]["Summary"]["CompliancePercent"] == 80


def test_load_local_scans_skips_unreadable_files_without_raising(tmp_path):
    (tmp_path / "broken.json").write_text("{not valid json")
    scans = load_local_scans(str(tmp_path))
    assert scans == {}


def test_load_local_scans_returns_empty_dict_when_no_dir_given():
    assert load_local_scans(None) == {}


def test_endpoints_rows_merges_matching_scan_by_hostname():
    endpoints = [{"name": "EpTestSQL", "platform": "Windows", "status": "Connected", "group_membership": []}]
    scans = {"eptestsql": {"Summary": {"CompliancePercent": 55.6, "Failed": 4}, "ScanTimestamp": "t"}}

    rows = build_endpoints_rows(endpoints, scans)

    assert rows[0]["cis_compliance_percent"] == 55.6
    assert rows[0]["cis_failed_checks"] == 4


def test_endpoints_rows_leaves_compliance_blank_when_no_scan_matches():
    endpoints = [{"name": "unscanned-host", "group_membership": []}]
    rows = build_endpoints_rows(endpoints, scans={})
    assert rows[0]["cis_compliance_percent"] == ""


def test_days_since_parses_action1_timestamp_format():
    assert days_since(_timestamp_days_ago(45)) == 45


def test_days_since_returns_none_for_missing_or_unparseable():
    assert days_since(None) is None
    assert days_since("") is None
    assert days_since("not-a-timestamp") is None


def test_disconnected_endpoint_not_seen_in_a_year_is_flagged_stale():
    endpoints = [
        {"name": "old-host", "status": "Disconnected", "last_seen": _timestamp_days_ago(365), "group_membership": []}
    ]
    rows = build_endpoints_rows(endpoints, scans={}, stale_days=30)
    assert rows[0]["stale"] is True
    assert rows[0]["days_since_last_seen"] == 365


def test_connected_endpoint_is_never_stale_even_with_old_last_seen():
    # A currently-Connected endpoint with a stale last_seen timestamp shouldn't happen in
    # practice, but status is the authoritative signal - don't flag it stale either way.
    endpoints = [
        {"name": "flaky-clock", "status": "Connected", "last_seen": _timestamp_days_ago(365), "group_membership": []}
    ]
    rows = build_endpoints_rows(endpoints, scans={}, stale_days=30)
    assert rows[0]["stale"] is False


def test_disconnected_but_recently_seen_endpoint_is_not_stale():
    endpoints = [
        {"name": "just-rebooted", "status": "Disconnected", "last_seen": _timestamp_days_ago(2), "group_membership": []}
    ]
    rows = build_endpoints_rows(endpoints, scans={}, stale_days=30)
    assert rows[0]["stale"] is False


def test_avg_compliance_in_summary_excludes_stale_endpoints(tmp_path):
    import generate_compliance_report as gcr

    endpoint_rows = [
        {"name": "fresh", "os": "Windows", "status": "Connected", "last_seen": "", "days_since_last_seen": 0,
         "stale": False, "reboot_required": "No", "update_status": "OK", "vulnerability_status": "OK",
         "cis_compliance_percent": 90.0},
        {"name": "stale", "os": "Windows", "status": "Disconnected", "last_seen": "", "days_since_last_seen": 400,
         "stale": True, "reboot_required": "No", "update_status": "OK", "vulnerability_status": "OK",
         "cis_compliance_percent": 10.0},
    ]
    out = tmp_path / "summary.html"
    gcr.write_summary_html(out, {"name": "Acme"}, endpoint_rows, [], [], has_scan_data=True, stale_days=30)
    html = out.read_text(encoding="utf-8")
    assert "90.0%" in html
    assert "1</span><span class=\"l\">Stale" in html
