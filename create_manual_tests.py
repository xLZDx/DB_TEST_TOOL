"""Create proper SQL test cases with correct column names and save to both tools."""
import httpx, json

DB_TOOL = "http://localhost:8550"
INTELLITEST = "http://localhost:8560"

# Correct test definitions based on actual CDS schema
TESTS = [
    # ── Row Counts ──
    {
        "name": "TXN total row count for stock movements on 2026-03-30",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72)",
        "expected_result": "20",
        "severity": "critical",
        "description": "Validates total TXN records for all 4 stock movement streams on business day 2026-03-30"
    },
    {
        "name": "TXN row count for S10REC (SRC_STM_ID=29)",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 29",
        "expected_result": "18",
        "severity": "critical",
        "description": "S10REC stream should have 18 transactions on 2026-03-30"
    },
    {
        "name": "TXN row count for S10DEL (SRC_STM_ID=30)",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 30",
        "expected_result": "2",
        "severity": "critical",
        "description": "S10DEL stream should have 2 transactions on 2026-03-30"
    },
    {
        "name": "TXN row count for S10TFRS (SRC_STM_ID=72)",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 72",
        "expected_result": "0",
        "severity": "medium",
        "description": "S10TFRS stream count on 2026-03-30 (may be 0 if no activity)"
    },
    {
        "name": "TXN row count for MULBULMT (SRC_STM_ID=71)",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 71",
        "expected_result": "0",
        "severity": "medium",
        "description": "MULBULMT stream count on 2026-03-30 (may be 0 if no activity)"
    },

    # ── Null checks on TXN target columns ──
    {
        "name": "EXEC_SBTP_ID not null for trailer-parsed streams",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 72) AND EXEC_SBTP_ID IS NULL",
        "expected_result": "0",
        "severity": "critical",
        "description": "Execution subtype ID must be populated for trailer-parsed streams (S10REC, S10DEL, S10TFRS)"
    },
    {
        "name": "SRC_PCS_TP_ID not null for all stock movement streams",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND SRC_PCS_TP_ID IS NULL",
        "expected_result": "0",
        "severity": "critical",
        "description": "Source processing type ID (CNX_IND equivalent) must be populated for all stock movements"
    },
    {
        "name": "TXN_TP_ID not null for stock movements",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_TP_ID IS NULL",
        "expected_result": "0",
        "severity": "critical",
        "description": "Transaction type ID must be populated"
    },
    {
        "name": "TXN_SBTP_ID null count for stock movements",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_SBTP_ID IS NULL",
        "expected_result": "20",
        "severity": "medium",
        "description": "Transaction subtype ID — check current population. All 20 are currently null on this date."
    },
    {
        "name": "AR_ID not null for stock movements",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND AR_ID IS NULL",
        "expected_result": "0",
        "severity": "high",
        "description": "Account relationship ID must be populated for all stock movement transactions"
    },
    {
        "name": "PD_ID not null for stock movements",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND PD_ID IS NULL",
        "expected_result": "0",
        "severity": "high",
        "description": "Product ID must be populated for all stock movement transactions"
    },

    # ── CDSM_RULE_MAP lookup table ──
    {
        "name": "CDSM_RULE_MAP has active rules",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CDS_STG_OWNER.CDSM_RULE_MAP",
        "expected_result": None,
        "severity": "high",
        "description": "Validates that the CDSM_RULE_MAP lookup table (CDSMANUL equivalent) has rules loaded"
    },

    # ── Cross-table: APA records ──
    {
        "name": "APA records exist for stock movement TXNs",
        "test_type": "custom_sql",
        "source_query": """SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)
AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.APA a WHERE a.TXN_ID = t.TXN_ID)""",
        "expected_result": "0",
        "severity": "high",
        "description": "Every stock movement TXN should have a corresponding APA record"
    },

    # ── Cross-table: FIP records ──
    {
        "name": "FIP records exist for stock movement TXNs",
        "test_type": "custom_sql",
        "source_query": """SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)
AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.FIP f WHERE f.TXN_ID = t.TXN_ID)""",
        "expected_result": "0",
        "severity": "high",
        "description": "Every stock movement TXN should have a corresponding FIP record"
    },

    # ── Cross-table: TXN_RLTNP ──
    {
        "name": "TXN_RLTNP relationships exist for stock movements",
        "test_type": "custom_sql",
        "source_query": """SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)
AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.TXN_RLTNP r WHERE r.TXN_ID = t.TXN_ID)""",
        "expected_result": "0",
        "severity": "medium",
        "description": "Stock movement TXNs should have relationship records"
    },

    # ── TXN data quality ──
    {
        "name": "SD (settlement date) not null for stock movements",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND SD IS NULL",
        "expected_result": "0",
        "severity": "medium",
        "description": "Settlement date should be populated for stock movements"
    },
    {
        "name": "TXN_SRC_KEY not null for stock movements",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_SRC_KEY IS NULL",
        "expected_result": "0",
        "severity": "high",
        "description": "Transaction source key must be populated"
    },
    {
        "name": "No duplicate TXN_SRC_KEY per SRC_STM_ID on business day",
        "test_type": "custom_sql",
        "source_query": """SELECT COUNT(*) AS CNT FROM (
    SELECT TXN_SRC_KEY, SRC_STM_ID, COUNT(*) AS C 
    FROM CCAL_OWNER.TXN 
    WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72)
    GROUP BY TXN_SRC_KEY, SRC_STM_ID HAVING COUNT(*) > 1
)""",
        "expected_result": "0",
        "severity": "high",
        "description": "Each TXN_SRC_KEY should be unique per SRC_STM_ID on a given business day"
    },

    # ── DATE_DIM consistency ──
    {
        "name": "TD exists in DATE_DIM",
        "test_type": "custom_sql",
        "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.DATE_DIM WHERE CAL_DT = DATE '2026-03-30'",
        "expected_result": "1",
        "severity": "low",
        "description": "Business day 2026-03-30 must exist in DATE_DIM calendar"
    },

    # ── SRC_PCS_TP_ID distribution ──
    {
        "name": "SRC_PCS_TP_ID distribution for stock movements",
        "test_type": "custom_sql",
        "source_query": """SELECT SRC_STM_ID, SRC_PCS_TP_ID, COUNT(*) AS CNT
FROM CCAL_OWNER.TXN 
WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72)
GROUP BY SRC_STM_ID, SRC_PCS_TP_ID
ORDER BY SRC_STM_ID, SRC_PCS_TP_ID""",
        "expected_result": None,
        "severity": "medium",
        "description": "Shows how source processing type is distributed across streams — validates ODI trailer logic"
    },
]


def save_to_dbtool():
    c = httpx.Client(base_url=DB_TOOL, timeout=30)
    # Create folder
    folder = c.post("/api/tests/folders", json={"name": "PBI1736268-Manual"}).json()
    fid = folder.get("id")
    print(f"[db-tool] Created folder: {fid}")
    
    created = []
    for t in TESTS:
        r = c.post("/api/tests", json={
            "name": t["name"],
            "test_type": "custom_sql",
            "source_datasource_id": 2,  # CDS in db-tool
            "source_query": t["source_query"],
            "expected_result": t["expected_result"],
            "severity": t["severity"],
            "description": t["description"],
            "is_ai_generated": False,
        }).json()
        created.append(r["id"])
    
    # Move to folder
    if fid and created:
        c.post("/api/tests/folders/move", json={"test_ids": created, "folder_id": fid})
    
    print(f"[db-tool] Created {len(created)} manual tests in folder {fid}")
    return created


def save_to_intellitest():
    c = httpx.Client(base_url=INTELLITEST, timeout=30)
    save = c.post("/api/tests/save-suite", json={
        "suite_name": "PBI1736268-Manual",
        "tests": TESTS,
        "source_datasource_id": 1  # CDS in IntelliTest
    }).json()
    print(f"[IntelliTest] Created {save.get('count')} tests in folder {save.get('folder_id')}")
    return save


if __name__ == "__main__":
    print("=== Saving manual tests to db-testing-tool ===")
    dt = save_to_dbtool()
    
    print("\n=== Saving manual tests to IntelliTest ===")
    it = save_to_intellitest()
    
    print(f"\nTotal: {len(TESTS)} manual tests saved to both tools")
