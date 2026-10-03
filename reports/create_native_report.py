"""Creates (or updates) a native Action1 Data Source + Custom Report from a local PowerShell
script - the console-native alternative to generate_compliance_report.py's external CSV/HTML.

Why this exists: Action1 "Data Sources" are just PowerShell scripts the agent runs on each
endpoint, returning one flat object whose properties become report columns (same mechanism as
Action1's own built-in "Windows Update Status" data source). Once published, any number of
Custom Reports can reference it and the data appears natively in the console under
Reports > Custom Reports - no external pipeline needed.

The request schema for both endpoints has several fields the OpenAPI spec doesn't mark
required but the API 400s without (discovered by trial, then confirmed by inspecting a report
created through the console UI):
    - Data source creation must use status="Draft" with columns=[]; publish with a follow-up
      PATCH that sets the real columns and status="Published".
    - Custom report creation requires simple_columns/summary_columns/drilldown_columns/
      filter_set/column_aliases *all* present (empty lists are fine except filter_set, which
      needs at least one filter).
    - data_sources entries need both "id" (int) and "self" (the data source's URL) - a bare id,
      or an {"id","type"} pair, both fail.

Usage:
    export ACTION1_CLIENT_ID=api-key-xxx@action1.com
    export ACTION1_CLIENT_SECRET=...
    export ACTION1_REGION=europe

    python create_native_report.py \
        --datasource-name "CIS Level 1 Compliance Scan" \
        --script cis_compliance_datasource.ps1 \
        --columns "Endpoint Name,Overall Compliance %,Firewall Status,Firewall Findings,..." \
        --report-name "CIS Level 1 Compliance" \
        [--datasource-id <id>]   # update an existing data source instead of creating one
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from action1_client import Action1Client  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasource-name", required=True)
    parser.add_argument("--datasource-description", default="")
    parser.add_argument("--script", required=True, help="Path to the PowerShell data source script")
    parser.add_argument("--columns", required=True, help="Comma-separated column names, in script output order")
    parser.add_argument("--datasource-id", help="Update this existing data source instead of creating a new one")
    parser.add_argument("--report-name", help="Also create a Custom Report referencing the data source")
    parser.add_argument("--report-description", default="")
    args = parser.parse_args()

    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    client_id = os.environ["ACTION1_CLIENT_ID"]
    client_secret = os.environ["ACTION1_CLIENT_SECRET"]
    region = os.environ.get("ACTION1_REGION", "north_america")

    with Action1Client(client_id, client_secret, region=region) as client:
        ds = client.publish_data_source(
            args.datasource_name, Path(args.script).read_text(encoding="utf-8"), columns,
            description=args.datasource_description, data_source_id=args.datasource_id,
        )
        print(f"Data source {ds['id']} ({ds['status']}, {len(ds['columns'])} columns)")
        if args.report_name:
            report = client.create_simple_report(
                args.report_name, ds, columns, description=args.report_description
            )
            print(f"Created report {report['id']!r} - {report['self']}")


if __name__ == "__main__":
    main()
