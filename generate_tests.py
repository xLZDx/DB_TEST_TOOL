"""Generate tests via both tools' AI endpoints and save them."""
import httpx, json, sys, time

DB_TOOL = "http://localhost:8550"
INTELLITEST = "http://localhost:8560"
CONV_ID = None  # Will be created

PROMPT = """Generate 20 executable Oracle SQL test cases for PBI 1736268: "Move trailer mapping logic for stock movements from HPNS to Oracle"

## PBI Context
- Record Type 7 (stock movements) only
- ODI now assigns: CNX_IND (source processing type), WS_SUBTYPE (transaction subtype), WS_EXECUTION_SUBTYPE (execution subtype)
- Previously done by HPNS CDSMANUC module
- CDSMANUL lookup table = CDS_STG_OWNER.CDSM_RULE_MAP in Oracle
- Source streams: S10DEL (SRC_STM_ID=30), S10REC (SRC_STM_ID=29), S10TFRS (SRC_STM_ID=72), MULBULMT (SRC_STM_ID=71)
- S10DEL/S10REC/S10TFRS use trailer parsing for subtype/execution_subtype 
- MULBULMT does NOT use trailer parsing
- Acceptance: same output as CDSMANUC for SIS stock movements
- Business day with data: TD = DATE '2026-03-30' has 20 TXN records

## Tables
- Target: CCAL_OWNER.TXN (main), CCAL_OWNER.APA, CCAL_OWNER.FIP, CCAL_OWNER.TXN_RLTNP
- Lookup: CDS_STG_OWNER.CDSM_RULE_MAP (trailer rules), CCAL_OWNER.DATE_DIM
- Key columns: TXN_ID, SRC_STM_ID, TXN_TP_ID, TXN_TP_CODE, WS_SUBTYPE, WS_EXECUTION_SUBTYPE, CNX_IND, TD, SD, AR_ID, PD_ID

## Referenced ODI Scenarios (attached as artifacts)
- SCEN_SSDS_AVY_PKG_LOAD_STCCCALQ_STG: Loads staging, applies CDSM_RULE_MAP trailer logic
- SCEN_SSDS_AVY_PKG_LOAD_SBDI_RT_MT: Loads from staging to target TXN/APA/FIP/TXN_RLTNP

## Required Tests
Each test MUST be a complete Oracle SELECT. Return JSON array where each element has:
- "name": descriptive test name
- "test_type": "custom_sql"
- "source_query": the Oracle SQL SELECT
- "expected_result": expected value (e.g. "0" for violation checks, "20" for counts)
- "severity": critical/high/medium/low
- "description": what this validates

Categories:
1. Row count per SRC_STM_ID for TD=DATE '2026-03-30'
2. NULL check on WS_SUBTYPE for trailer-parsed streams (29,30,72)
3. NULL check on WS_EXECUTION_SUBTYPE
4. NULL check on CNX_IND
5. CDSM_RULE_MAP has rules for each source
6. APA records exist for TXN
7. FIP records exist for TXN
8. TXN_RLTNP relationships exist
9. TXN_TP_CODE valid
10. Date consistency TD vs DATE_DIM"""


def generate_dbtool():
    """Generate tests via db-testing-tool AI Chat."""
    c = httpx.Client(base_url=DB_TOOL, timeout=180)
    
    # Create conversation
    conv = c.post("/api/chat/conversations", json={"title": "PBI 1736268 Tests"}).json()
    conv_id = conv["conversation"]["id"]
    print(f"[db-tool] Conversation: {conv_id}")
    
    # Send message with artifacts
    msg = c.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "message": PROMPT,
        "artifact_ids": ["407f10df", "0c62703d"]
    }).json()
    
    response = msg.get("content", "") or msg.get("response", "")
    print(f"[db-tool] Response length: {len(response)}")
    print(f"[db-tool] Response preview: {response[:300]}")
    
    # Extract JSON from response
    tests = extract_tests(response)
    print(f"[db-tool] Extracted {len(tests)} tests")
    
    if tests:
        # Save as suite to db-testing-tool
        save = c.post("/api/tests/create-selected", json={"tests": [
            {
                "name": t.get("name", "Test"),
                "test_type": "custom_sql",
                "source_datasource_id": 2,  # CDS in db-tool
                "source_query": t.get("source_query") or t.get("sql_validation") or t.get("sql", ""),
                "expected_result": str(t.get("expected_result", "")),
                "severity": t.get("severity", "medium"),
                "description": t.get("description", ""),
                "is_ai_generated": True
            } for t in tests
        ]}).json()
        print(f"[db-tool] Saved: {save}")
        
        # Create folder and move tests
        folder = c.post("/api/tests/folders", json={"name": "PBI1736268-AIChat"}).json()
        folder_id = folder.get("id")
        if folder_id and save.get("tests"):
            test_ids = [t["id"] for t in save["tests"]]
            c.post("/api/tests/folders/move", json={"test_ids": test_ids, "folder_id": folder_id})
            print(f"[db-tool] Moved {len(test_ids)} tests to folder {folder_id}")
    
    return tests


def generate_intellitest():
    """Generate tests via IntelliTest AI endpoint and save to DB."""
    c = httpx.Client(base_url=INTELLITEST, timeout=180)
    
    result = c.post("/api/tests/generate", json={
        "prompt": PROMPT,
        "target_table": "CCAL_OWNER.TXN",
        "source_table": "CDS_STG_OWNER.STCCCALQ_STG",
        "artifact_ids": ["ebdb5051", "f43120c6"],
        "multi_layer": True
    }).json()
    
    tests = result.get("tests", [])
    print(f"[IntelliTest] Generated {len(tests)} tests")
    
    if tests:
        # Save as suite with CDS datasource (id=1 in IntelliTest)
        save = c.post("/api/tests/save-suite", json={
            "suite_name": "PBI1736268-AIGenerate",
            "tests": tests,
            "source_datasource_id": 1  # CDS in IntelliTest
        }).json()
        print(f"[IntelliTest] Saved: {save.get('count')} tests to folder {save.get('folder_id')}")
    
    return tests


def extract_tests(text):
    """Extract JSON array of tests from AI response text."""
    import re
    # Try to find JSON array in the text
    patterns = [
        r'```json\s*(\[.*?\])\s*```',
        r'```\s*(\[.*?\])\s*```',
        r'(\[\s*\{.*?\}\s*\])',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    # Try parsing the whole thing
    try:
        return json.loads(text)
    except:
        pass
    return []


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    
    if mode in ("dbtool", "both"):
        print("=== db-testing-tool AI Chat ===")
        try:
            dt = generate_dbtool()
        except Exception as e:
            print(f"[db-tool] ERROR: {e}")
            dt = []
    
    if mode in ("intellitest", "both"):
        print("\n=== IntelliTest AI Generate ===")
        try:
            it = generate_intellitest()
        except Exception as e:
            print(f"[IntelliTest] ERROR: {e}")
            it = []
    
    print("\n=== Summary ===")
    if mode in ("dbtool", "both"):
        print(f"db-testing-tool: {len(dt)} tests")
    if mode in ("intellitest", "both"):
        print(f"IntelliTest: {len(it)} tests")
