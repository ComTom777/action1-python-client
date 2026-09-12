# action1-client

**Unofficial** — not affiliated with, endorsed by, or supported by Action1 Corporation. A small,
dependency-light Python client for the [Action1](https://www.action1.com/) RMM REST API (v3.0).

Cross-platform (Linux/macOS/Windows) — built as the Python counterpart to
[PSAction1](https://github.com/ComTom777/PSAction1), for cases where a PowerShell dependency
isn't a good fit (e.g. an [MCP server](../action1-mcp-server)).

## Install

```bash
pip install -e .
```

## Usage

```python
from action1_client import Action1Client

with Action1Client(
    client_id="api-key-....@action1.com",
    client_secret="...",
    region="europe",  # or "north_america" / "australia"
) as client:
    for org in client.list_organizations():
        print(org["id"], org["name"])

    endpoints = client.list_endpoints(org_id="...")
    client.add_endpoint_group_members(org_id="...", group_id="...", endpoint_ids=["..."])
```

See `examples/list_organizations.py` for a runnable version (reads credentials from environment
variables).

Authentication is OAuth2 client-credentials: the client posts to `/oauth2/token` on first use
and transparently refreshes the token before it expires. Errors from the API surface as
`Action1APIError` (HTTP error responses, with `.status_code` and a message pulled from Action1's
`user_message`/`developer_message` body) or `Action1AuthError` (the token exchange itself
failed).

## Custom reports

`reports/generate_compliance_report.py` builds an org-wide compliance report combining
Action1's native patch/vulnerability data with local CIS hardening scan results (from the
`Check-*.ps1` / `Invoke-ComplianceScan.ps1` script library):

```bash
export ACTION1_CLIENT_ID=api-key-xxx@action1.com
export ACTION1_CLIENT_SECRET=...
export ACTION1_REGION=europe   # optional, default north_america

python reports/generate_compliance_report.py --out ./report \
    --scans-dir /path/to/collected/scan/json/files   # optional
```

Produces `endpoints.csv`, `vulnerabilities.csv`, `missing_updates.csv`, and a one-page
`summary.html`. See the module docstring for why patch/vulnerability data comes from the API
rather than a local script.

### Native console reports (no external pipeline)

For OS-hardening checks (things Action1 doesn't track natively - see the note above), you can
instead publish the check script as an Action1 **Data Source** and build a **Custom Report** on
top of it, so the data shows up directly in `Reports > Custom Reports` in the console, collected
by the agent on its own schedule - no CSV/HTML file to distribute.

`reports/cis_compliance_datasource.ps1` is a ready-to-use example: the CIS Level 1 checks
condensed into one flat-output, cross-platform script (Windows checks run on Windows, Linux/
macOS equivalents run there, everything else reports `NotApplicable`).

```bash
python reports/create_native_report.py \
    --datasource-name "CIS Level 1 Compliance Scan" \
    --script reports/cis_compliance_datasource.ps1 \
    --columns "Endpoint Name,Overall Compliance %,Firewall Status,Firewall Findings,..." \
    --report-name "CIS Level 1 Compliance"

# Update an existing data source in place (keeps the same id, so reports built on it don't break):
python reports/create_native_report.py \
    --datasource-id <id> --datasource-name "..." --script ... --columns "..."
```

See [`reports/README.md`](reports/README.md) for the full step-by-step guide, including every
undocumented API quirk this reverse-engineered (required-but-unmarked fields, the exact
`data_sources`/`simple_columns`/`filter_set` shapes, how updating a data source's columns
auto-propagates into reports built on it).

## Scope

This client covers the full ~141-operation API surface (organizations, endpoints, endpoint groups
+ membership, vulnerabilities, scripts, packages incl. chunked binary upload, automations, updates,
installed software, data sources, settings, reports, roles, users, enterprise, audit).
`coverage_check.py` diffs the implemented methods against Action1's OpenAPI spec to keep it
that way (maintainer-only — it points at a local spec file not included in this repo). Adding a
new resource is mechanical: add a method to `Action1Client` in `client.py` that calls
`self.get/post/patch/delete` or `self.paginate` with the right path.

## Development

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -e ".[dev]"
pytest
```

Tests mock the HTTP layer with `respx` — no live Action1 credentials are needed to run them.
