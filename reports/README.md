# How to build a native Action1 report

A step-by-step guide to publishing a custom check as a report that lives in the Action1
console (`Reports > Custom Reports`), collected by the agent on its own schedule — no external
CSV/HTML pipeline. Written up so the next person (or the next session) doesn't have to
re-discover the undocumented parts of this flow by trial and error against a live tenant.

## The concept

An Action1 **Data Source** is not a place you push data into — it's a script (PowerShell or,
for Action1's own built-ins, NodeJS) that runs **on the endpoint** via the agent and returns one
flat object. Each property of that object becomes a report column. This is the exact mechanism
behind Action1's own built-in data sources (e.g. "Windows Update Status") — nothing special
about ours.

A **Custom Report** is a view on top of one or more data sources: which columns to show, how to
filter/summarize them, all editable later in the console UI.

```
check script  →  Data Source (script + declared columns)  →  Custom Report (columns + filter)
                  runs on every endpoint, agent-collected      shows up in Reports > Custom Reports
```

## Step 1 — Write the script

Requirements for the script (`language: "PowerShell"`):

- End with a **single bare `[PSCustomObject]`** expression (not `Write-Output`, not multiple
  objects — one row per endpoint per run). Property order doesn't matter; property *names* are
  what get matched to declared columns.
- If it needs to run on Linux/macOS too, detect the OS with `$IsWindows`/`$IsLinux`/`$IsMacOS`
  (present since pwsh 6+) and branch — see `cis_compliance_datasource.ps1` for the pattern. Give
  every column a value on every OS (use `'NotApplicable'` for checks that don't apply on that
  platform) rather than leaving properties unset.
- Include an **`A1_Key`** property: the row's unique key (`'none'` when the script returns
  one row per endpoint; use something like a SID or index for multi-row output). Without it the
  agent's result is rejected with "Missing key column A1_Key in query output" (shows up in
  `list_report_errors`). Don't list `A1_Key` in the data source's `columns`.
- Wrap each check in try/catch — one failing check (e.g. `Get-BitLockerVolume` needing
  elevation) shouldn't blank out the rest of the row.

`cis_compliance_datasource.ps1` in this folder is a complete, working example.

## Step 2 — Publish it as a Data Source

Two API calls, not one — **creating with real columns directly fails**:

```python
# 1. Create as Draft with EMPTY columns. (Sending real columns here 400s: "Property name
#    'columns' must be an Array and must be empty for 'Draft' status".)
draft = client.create_data_source(
    name="...", description="...", language="PowerShell",
    script_text=open("check.ps1").read(), columns=[], status="Draft",
)

# 2. Publish: PATCH with the real column list and status="Published" together.
ds = client.update_data_source(draft["id"], columns=[...], status="Published")
```

Column names in the list must exactly match the script's output property names (case-sensitive
string match). `Endpoint Name` is implicit — the agent injects it — but the platform still wants
it listed explicitly in `columns` and later in the report's `simple_columns`.

## Step 3 — Create the Custom Report

This is the part that isn't documented in the OpenAPI spec at all — the spec doesn't mark any of
these as required, but the API 400s without every one of them present:

| Field | Gotcha |
|---|---|
| `data_sources` | Must be `["/API/data_sources/all/<id>"]` (as in the spec's example). `{"id", "self"}` objects, a bare id, or `{"id","type"}` all fail - as of 2026-10 the object form returns an opaque 500. |
| `simple_columns` | **Not** a list of strings — a list of `{"name", "enabled": "yes", "sort": "none", "data_source_id": <int>}`. |
| `summary_columns` | Must be present; `[]` is accepted. |
| `drilldown_columns` | Must be present; `[]` is accepted. |
| `filter_set` | Must be present with **at least one filter**: `{"filters": [{"name": "Endpoint Name", "value": "*", "operator": "=", "data_source_id": <int>}], "filter_logic": ""}` (this is the UI's default "match everything" filter). |
| `column_aliases` | Must be present; `[]` is accepted. |

```python
client.create_custom_report(
    name="...", description="...",
    data_sources=[f"/API/data_sources/all/{ds['id']}"],
    simple_columns=[
        {"name": c, "enabled": "yes", "sort": "none", "data_source_id": ds["id"]}
        for c in columns
    ],
    summary_columns=[],
    drilldown_columns=[],
    filter_set={
        "filters": [{"name": "Endpoint Name", "value": "*", "operator": "=", "data_source_id": ds["id"]}],
        "filter_logic": "",
    },
    column_aliases=[],
)
```

## Do all of this in one command

`client.publish_data_source()` + `client.create_simple_report()` implement steps 2–3;
`create_native_report.py` wraps them (given a script file and column list):

```bash
export ACTION1_CLIENT_ID=api-key-xxx@action1.com
export ACTION1_CLIENT_SECRET=...
export ACTION1_REGION=europe

python create_native_report.py \
    --datasource-name "CIS Level 1 Compliance Scan" \
    --script cis_compliance_datasource.ps1 \
    --columns "Endpoint Name,Overall Compliance %,Firewall Status,Firewall Findings,..." \
    --report-name "CIS Level 1 Compliance"
```

## Updating an existing check without breaking its report

Reports with `simple: "yes"` (the default, simple column-picker reports) **auto-sync their
column list from the data source** — adding new columns to the data source and re-`PATCH`ing it
makes them show up in every report built on it automatically, no report-side edit needed.
Confirmed live: adding two new columns (`SSH Exposure`, `FileVault`) to an existing, in-use data
source picked them up in its report immediately, with the original 17 columns untouched.

To update in place, reuse the same data source id and skip the create step:

```bash
python create_native_report.py \
    --datasource-id <existing-id> \
    --datasource-name "..." --script check.ps1 --columns "..."
    # omit --report-name - no new report needed, existing ones auto-pick-up new columns
```

Don't rename existing columns if a report already references them by name — add new ones
instead (see how `cis_compliance_datasource.ps1` added `SSH Exposure`/`FileVault` alongside the
Windows-only `RDP Exposure`/`BitLocker` rather than renaming them to something OS-neutral).

## Finding a report you (or someone else) created in the console

There's no `GET /reports/all/custom` list endpoint, and the category object's `children` URL
field isn't part of the public API (it 403s with a bearer token — it's a console-internal link).
The reliable way to find a report's id from the API is the org-wide search endpoint:

```python
results = client.search(org_id, "<part of the report name>")
# results include {"type": "Report", "id": "...", "data_sources": [...], ...}
```

Then `client.get_report_or_category(report_id)` for the full object.
