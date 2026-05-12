import requests

BASE='http://localhost:8550'
DS=2

sql = """
SELECT txn_src_key, to_location, from_location, shares, trailer, option_cls,
    security_type, product_category, term_name,
       ws_subtype, ws_cnx_ind, ws_execution_subtype, ws_exception_text, record_type_multi
FROM CDS_STG_OWNER.STCCCALQ_GG_VW
WHERE ROWNUM <= 3
"""

r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":10},timeout=180)
print('status',r.status_code)
print(r.text[:4000])
