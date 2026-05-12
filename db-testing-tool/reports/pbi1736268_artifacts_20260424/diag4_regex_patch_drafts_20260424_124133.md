# Diagnostic Pack 4 - Regex Patch Drafts

Generated: 20260424_124133
Business date: 2026-03-30
Streams: 29,30,71,72

These are draft candidates only. No DB update was performed.

## DIRECT ROLLOVER - STOCK
- Proposed rule text: `DIRECT ROLLOVER - STOCK`
- Proposed regex: `^DIRECT[[:space:]]+ROLLOVER[[:space:]]+\-[[:space:]]+STOCK([[:space:]]*)$`
- Prefix TXN count: `15`
- Regex matched TXN count (draft regex): `15`
- Top inheritance options:
  - map_id=1643, txn_sbtp_cd=TSTP0524, exec_sbtp_cd=None, cnx_ind=None
  - map_id=836, txn_sbtp_cd=TSTP0524, exec_sbtp_cd=None, cnx_ind=None
  - map_id=1640, txn_sbtp_cd=TSTP0524, exec_sbtp_cd=None, cnx_ind=None

## SECURITY RECEIVED IN BRANCH
- Proposed rule text: `SECURITY RECEIVED IN BRANCH`
- Proposed regex: `^SECURITY[[:space:]]+RECEIVED[[:space:]]+IN[[:space:]]+BRANCH([[:space:]]*)$`
- Prefix TXN count: `2`
- Regex matched TXN count (draft regex): `2`
- Top inheritance options:
  - map_id=1603, txn_sbtp_cd=None, exec_sbtp_cd=ESTP0014, cnx_ind=None
  - map_id=2010, txn_sbtp_cd=TSTP0912, exec_sbtp_cd=ESTP0012, cnx_ind=None
  - map_id=1969, txn_sbtp_cd=TSTP0912, exec_sbtp_cd=ESTP0012, cnx_ind=None

## ACAT TEST
- Proposed rule text: `ACAT TEST`
- Proposed regex: `^ACAT[[:space:]]+TEST([[:space:]]*)$`
- Prefix TXN count: `1`
- Regex matched TXN count (draft regex): `1`
- Top inheritance options:
  - map_id=1813, txn_sbtp_cd=None, exec_sbtp_cd=None, cnx_ind=REVERSAL
  - map_id=1827, txn_sbtp_cd=None, exec_sbtp_cd=None, cnx_ind=REVERSAL
  - map_id=1610, txn_sbtp_cd=TSTP0981, exec_sbtp_cd=ESTP0014, cnx_ind=REVERSAL
