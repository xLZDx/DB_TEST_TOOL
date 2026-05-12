from app.services.ai_service import _normalize_etl_mapping_spec_payload, _parse_json_response_text


def test_parse_json_response_text_handles_fenced_json_with_prose_header():
    payload = """Below is the standardized mapping specification.

```json
{
  "source_tables": ["CDS_STG_OWNER.STCCCALQ_GG_VW"],
  "target_tables": ["CCAL_OWNER.TXN"],
  "business_keys": ["ACTY_ID"],
  "join_conditions": "S.ACTY_ID = T.ACTY_ID",
  "mappings": [],
  "filters": "S.ACTV_F = 'Y'"
}
```
"""

    parsed = _parse_json_response_text(payload, expected="object")

    assert parsed["source_tables"] == ["CDS_STG_OWNER.STCCCALQ_GG_VW"]
    assert parsed["target_tables"] == ["CCAL_OWNER.TXN"]


def test_parse_json_response_text_handles_embedded_json_array():
    payload = """I generated the following tests for the ODI flow.
[
  {
    "name": "Validate core join",
    "test_type": "value_match",
    "severity": "high",
    "description": "Compare staging to target on ACTY_ID",
    "db_dialect": "oracle",
    "source_query": "SELECT 1 FROM DUAL",
    "target_query": "SELECT 1 FROM DUAL",
    "expected_result": "0"
  }
]
Please review them.
"""

    parsed = _parse_json_response_text(payload, expected="array")

    assert len(parsed) == 1
    assert parsed[0]["name"] == "Validate core join"


def test_normalize_etl_mapping_spec_payload_handles_wrapped_title_case_keys():
    payload = {
      "EtlMappingSpec": {
        "Source Tables": ["CDS_STG_OWNER.STCCCALQ_GG_VW"],
        "Target Tables": ["CCAL_OWNER.TXN"],
        "Business Keys": ["ACTY_ID"],
        "Join Conditions": "S.ACTY_ID = T.ACTY_ID",
        "Mappings": [
          {
            "Source Column": "TRAILER_TXT",
            "Target Column": "DEAL_DESCRIPTION",
            "Transformation": "Trailer parsing via rule map",
            "Rule Type": "lookup",
          }
        ],
        "Filters": "S.ACTV_F = 'Y'"
      }
    }

    normalized = _normalize_etl_mapping_spec_payload(payload)

    assert normalized["source_tables"] == ["CDS_STG_OWNER.STCCCALQ_GG_VW"]
    assert normalized["target_tables"] == ["CCAL_OWNER.TXN"]
    assert normalized["join_conditions"] == "S.ACTY_ID = T.ACTY_ID"
    assert normalized["mappings"][0]["source_column"] == "TRAILER_TXT"