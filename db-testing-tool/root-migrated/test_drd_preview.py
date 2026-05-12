"""Test DRD preview and import endpoints."""
import requests
import json

BASE = "http://127.0.0.1:8550"
CSV_PATH = r"c:\GIT_Repo\DRD_Activity_Fact(Table-View).csv"

def test_preview():
    print("=" * 60)
    print("TEST: DRD Preview")
    print("=" * 60)
    with open(CSV_PATH, "rb") as f:
        content = f.read()
    files = {"file": ("DRD_Activity_Fact(Table-View).csv", content, "text/csv")}
    r = requests.post(f"{BASE}/api/mappings/drd-preview", files=files)
    d = r.json()
    print(f"Status: {r.status_code}")
    print(f"DRD format: {d.get('is_drd_format')}")
    print(f"Total rows: {d.get('total_rows')}")
    print(f"Metadata:")
    for k, v in d.get("metadata", {}).items():
        if v:
            print(f"  {k}: {v}")
    print(f"Suggested columns ({len(d.get('suggested_columns', []))}):")
    for c in d.get("suggested_columns", []):
        sel = "x" if c["selected"] else " "
        print(f"  [{sel}] {c['field']:30s} -> {c['header'][:60]}")
    print()
    return d


def test_import(preview_data):
    print("=" * 60)
    print("TEST: DRD Import")
    print("=" * 60)
    
    # Use selected fields from preview
    selected = [c["field"] for c in preview_data.get("suggested_columns", []) if c["selected"]]
    print(f"Selected fields: {', '.join(selected)}")
    
    with open(CSV_PATH, "rb") as f:
        content = f.read()
    files = {"file": ("DRD_Activity_Fact(Table-View).csv", content, "text/csv")}
    
    params = {
        "selected_fields": ",".join(selected),
        "target_schema": "SSDS_DAL_OWNER",
        "target_table": "ACTIVITY_FACT_V",
        "source_datasource_id": 1,
        "target_datasource_id": 1,
    }
    
    r = requests.post(f"{BASE}/api/mappings/drd-import", files=files, params=params)
    d = r.json()
    print(f"Status: {r.status_code}")
    print(f"Response status: {d.get('status')}")
    print(f"Message: {d.get('message')}")
    print(f"Rules created: {len(d.get('created_rules', []))}")
    for rule in d.get("created_rules", []):
        print(f"  - {rule['name']}")
    print(f"Record count tests: {d.get('record_count_tests', 0)}")
    print(f"Mapping validation tests: {d.get('mapping_validation_tests', 0)}")
    print(f"Column mappings analyzed: {d.get('column_mappings_count', 0)}")
    
    if d.get("errors"):
        print(f"Errors ({len(d['errors'])}):")
        for e in d["errors"][:5]:
            print(f"  - {e}")
    print()


if __name__ == "__main__":
    preview = test_preview()
    test_import(preview)
    print("Done!")
