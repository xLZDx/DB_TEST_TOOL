import requests
import time
from datetime import datetime

DB_BASE = 'http://localhost:8550'
IT_BASE = 'http://localhost:8560'

DATE = "2026-03-30"
STREAMS = "29,30,71,72"

TESTS = [
    {
        "name": "Trailer parsing base join row count (TXN <-> STCCCALQ_GG_VW)",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS})",
        "expected": "20",
    },
    {
        "name": "WS_EXECUTION_SUBTYPE populated in source view",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_EXECUTION_SUBTYPE IS NULL",
        "expected": "0",
    },
    {
        "name": "WS_CNX_IND populated in source view",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_CNX_IND IS NULL",
        "expected": "0",
    },
    {
        "name": "EXEC_SBTP_ID mapped from WS_EXECUTION_SUBTYPE via CL_VAL",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY LEFT JOIN CCAL_OWNER.CL_VAL cv ON cv.CL_VAL_CODE=s.WS_EXECUTION_SUBTYPE WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_EXECUTION_SUBTYPE IS NOT NULL AND NVL(t.EXEC_SBTP_ID,-1)<>NVL(cv.CL_VAL_ID,-1)",
        "expected": "0",
    },
    {
        "name": "SRC_PCS_TP_ID mapped from WS_CNX_IND via SRC_PCS_TP",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY LEFT JOIN CCAL_OWNER.SRC_PCS_TP p ON p.SRC_PCS_TP_CODE=s.WS_CNX_IND WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_CNX_IND IS NOT NULL AND NVL(t.SRC_PCS_TP_ID,-1)<>NVL(p.SRC_PCS_TP_ID,-1)",
        "expected": "0",
    },
    {
        "name": "TXN_SBTP_ID mapped from WS_SUBTYPE when present",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY LEFT JOIN CCAL_OWNER.CL_VAL cv ON cv.CL_VAL_CODE=s.WS_SUBTYPE WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_SUBTYPE IS NOT NULL AND NVL(t.TXN_SBTP_ID,-1)<>NVL(cv.CL_VAL_ID,-1)",
        "expected": "0",
    },
    {
        "name": "TXN_SBTP_ID stays NULL when WS_SUBTYPE is NULL",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_SUBTYPE IS NULL AND t.TXN_SBTP_ID IS NOT NULL",
        "expected": "0",
    },
    {
        "name": "WS_TRAILER_RULE_TEXT_MATCH links to active CDSM_RULE_MAP row",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY LEFT JOIN CCAL_OWNER.CDSM_RULE_MAP m ON m.TRLR_RULE_TXT=s.WS_TRAILER_RULE_TEXT_MATCH AND m.ACTV_F='Y' WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND s.WS_TRAILER_RULE_TEXT_MATCH IS NOT NULL AND m.CDSM_RULE_MAP_ID IS NULL",
        "expected": "0",
    },
    {
        "name": "When rule text present, WS_EXECUTION_SUBTYPE matches CDSM_RULE_MAP.EXEC_SBTP_CD",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY JOIN CCAL_OWNER.CDSM_RULE_MAP m ON m.TRLR_RULE_TXT=s.WS_TRAILER_RULE_TEXT_MATCH AND m.ACTV_F='Y' WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND m.EXEC_SBTP_CD IS NOT NULL AND NVL(s.WS_EXECUTION_SUBTYPE,'~')<>NVL(m.EXEC_SBTP_CD,'~')",
        "expected": "0",
    },
    {
        "name": "APA exists for each parsed TXN",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY LEFT JOIN CCAL_OWNER.APA a ON a.EXEC_ID=t.TXN_ID WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND a.APA_ID IS NULL",
        "expected": "0",
    },
    {
        "name": "FIP rows for parsed TXNs have valid APA",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.FIP f LEFT JOIN CCAL_OWNER.APA a ON a.APA_ID=f.APA_ID LEFT JOIN CCAL_OWNER.TXN t ON t.TXN_ID=a.EXEC_ID WHERE t.TD=DATE '{DATE}' AND t.SRC_STM_ID IN ({STREAMS}) AND a.APA_ID IS NULL",
        "expected": "0",
    },
    {
        "name": "TXN_RLTNP rows for parsed TXNs have valid SRC/TRGT txns",
        "sql": f"SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN_RLTNP r JOIN CCAL_OWNER.TXN bt ON (bt.TXN_ID=r.SRC_TXN_ID OR bt.TXN_ID=r.TRGT_TXN_ID) LEFT JOIN CCAL_OWNER.TXN s ON s.TXN_ID=r.SRC_TXN_ID LEFT JOIN CCAL_OWNER.TXN t ON t.TXN_ID=r.TRGT_TXN_ID WHERE bt.TD=DATE '{DATE}' AND bt.SRC_STM_ID IN ({STREAMS}) AND (s.TXN_ID IS NULL OR t.TXN_ID IS NULL)",
        "expected": "0",
    },
]


def create_folder(base, name):
    r = requests.post(f"{base}/api/tests/folders", json={"name": name}, timeout=30)
    r.raise_for_status()
    return r.json()


def create_test(base, folder_id, test, source_ds):
    payload = {
        "name": test["name"],
        "test_type": "custom_sql",
        "source_datasource_id": source_ds,
        "target_datasource_id": None,
        "source_query": test["sql"],
        "target_query": None,
        "expected_result": test["expected"],
        "tolerance": 0,
        "severity": "critical",
        "description": "Trailer parsing validation (source->rule->target join logic)",
        "is_ai_generated": False,
        "folder_id": folder_id,
    }
    r = requests.post(f"{base}/api/tests", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def run_dbtool_batch(ids):
    r = requests.post(f"{DB_BASE}/api/tests/run-batch/start", json={"test_ids": ids}, timeout=30)
    r.raise_for_status()
    batch = r.json()
    bid = batch["batch_id"]
    for _ in range(30):
        time.sleep(2)
        s = requests.get(f"{DB_BASE}/api/tests/run-batch/status/{bid}", timeout=30)
        s.raise_for_status()
        data = s.json()
        if data.get("status") in ("completed", "stopped", "error"):
            return data
    return {"status": "timeout", "batch_id": bid}


def run_intellitest_batch(ids):
    r = requests.post(f"{IT_BASE}/api/tests/run-batch", json={"test_ids": ids}, timeout=300)
    r.raise_for_status()
    return r.json()


def main():
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    db_folder_name = f"PBI1736268-TrailerParsing-v2-DB-{stamp}"
    it_folder_name = f"PBI1736268-TrailerParsing-v2-IT-{stamp}"

    db_folder = create_folder(DB_BASE, db_folder_name)
    it_folder = create_folder(IT_BASE, it_folder_name)

    db_ids = []
    it_ids = []

    for t in TESTS:
        db_created = create_test(DB_BASE, db_folder['id'], t, source_ds=2)
        it_created = create_test(IT_BASE, it_folder['id'], t, source_ds=1)
        db_ids.append(db_created['id'])
        it_ids.append(it_created['id'])

    db_run = run_dbtool_batch(db_ids)
    it_run = run_intellitest_batch(it_ids)

    print('DB folder:', db_folder)
    print('IT folder:', it_folder)
    print('DB test ids:', db_ids)
    print('IT test ids:', it_ids)
    print('DB run summary:', db_run)
    print('IT run summary:', it_run)


if __name__ == '__main__':
    main()
