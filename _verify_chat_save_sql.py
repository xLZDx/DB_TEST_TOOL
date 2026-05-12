import requests
BASE='http://localhost:8550'

# create conversation
c=requests.post(f"{BASE}/api/chat/conversations",json={"title":"verify-save-sql"},timeout=30)
conv=c.json()['conversation']['id']

# ask for one SQL block
msg={
  "conversation_id": conv,
  "message": "Generate exactly one Oracle SQL test as ```sql code block for counting stock movement rows in TXN for TD=2026-03-30.",
  "artifact_ids": [],
  "mode": "test_generation"
}
r=requests.post(f"{BASE}/api/chat/message",json=msg,timeout=120)
print('chat',r.status_code)
print((r.json().get('content') or '')[:400])

# save sql tests
s=requests.post(f"{BASE}/api/chat/conversations/{conv}/save-sql-tests",json={
    "source_datasource_id":2,
    "folder_name":"_verify_chat_save_sql",
    "severity":"high",
    "expected_result":"0",
    "only_select":True
},timeout=60)
print('save',s.status_code)
print(s.text)
