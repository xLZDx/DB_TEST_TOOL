-- Draft-only regex patch candidates for PBI 1736268
-- DO NOT execute directly in production without business sign-off.

-- Prefix: DIRECT ROLLOVER - STOCK
-- Validation: prefix_txn_cnt=15, regex_match_txn_cnt=15
-- Option A: update existing closest rule (replace <TARGET_RULE_ID>)
UPDATE CCAL_OWNER.CDSM_RULE_MAP
   SET TRLR_RULE_TXT = 'DIRECT ROLLOVER - STOCK',
       REGEX_PATT   = '^DIRECT[[:space:]]+ROLLOVER[[:space:]]+\-[[:space:]]+STOCK([[:space:]]*)$',
       LAST_UDT_DTM = SYSTIMESTAMP,
       LAST_UDT_USR_NM = 'PBI1736268_DIAG_DRAFT'
 WHERE CDSM_RULE_MAP_ID = <TARGET_RULE_ID>;

-- Option B: insert new active rule row based on approved business mapping
-- INSERT INTO CCAL_OWNER.CDSM_RULE_MAP (...columns...) VALUES (...);

-- Prefix: SECURITY RECEIVED IN BRANCH
-- Validation: prefix_txn_cnt=2, regex_match_txn_cnt=2
-- Option A: update existing closest rule (replace <TARGET_RULE_ID>)
UPDATE CCAL_OWNER.CDSM_RULE_MAP
   SET TRLR_RULE_TXT = 'SECURITY RECEIVED IN BRANCH',
       REGEX_PATT   = '^SECURITY[[:space:]]+RECEIVED[[:space:]]+IN[[:space:]]+BRANCH([[:space:]]*)$',
       LAST_UDT_DTM = SYSTIMESTAMP,
       LAST_UDT_USR_NM = 'PBI1736268_DIAG_DRAFT'
 WHERE CDSM_RULE_MAP_ID = <TARGET_RULE_ID>;

-- Option B: insert new active rule row based on approved business mapping
-- INSERT INTO CCAL_OWNER.CDSM_RULE_MAP (...columns...) VALUES (...);

-- Prefix: ACAT TEST
-- Validation: prefix_txn_cnt=1, regex_match_txn_cnt=1
-- Option A: update existing closest rule (replace <TARGET_RULE_ID>)
UPDATE CCAL_OWNER.CDSM_RULE_MAP
   SET TRLR_RULE_TXT = 'ACAT TEST',
       REGEX_PATT   = '^ACAT[[:space:]]+TEST([[:space:]]*)$',
       LAST_UDT_DTM = SYSTIMESTAMP,
       LAST_UDT_USR_NM = 'PBI1736268_DIAG_DRAFT'
 WHERE CDSM_RULE_MAP_ID = <TARGET_RULE_ID>;

-- Option B: insert new active rule row based on approved business mapping
-- INSERT INTO CCAL_OWNER.CDSM_RULE_MAP (...columns...) VALUES (...);

