# MCP Servers Configuration

## Oracle MCP Server

The DB Testing Tool integrates with Oracle databases via its built-in datasource layer.
For enhanced AI-agent interaction, configure these MCP-compatible endpoints:

### Built-in Oracle Integration
The tool provides Oracle connectivity through SQLAlchemy + cx_Oracle:
- **Schema Discovery**: `GET /api/datasources/{id}/schemas` → list all schemas
- **Table Discovery**: `GET /api/datasources/{id}/tables?schema=X` → list tables in schema
- **Column Discovery**: `GET /api/datasources/{id}/columns?schema=X&table=Y` → column metadata
- **SQL Execution**: `POST /api/datasources/{id}/execute` → run arbitrary SQL
- **PDM Load**: `POST /api/datasources/{id}/pdm/refresh` → refresh Physical Data Model

### MCP-Style Tool Endpoints
These endpoints follow the MCP tool pattern for agent consumption:

| Tool | Endpoint | Description |
|------|----------|-------------|
| `oracle_query` | `POST /api/datasources/{id}/execute` | Execute SELECT/DML on Oracle |
| `oracle_describe` | `GET /api/datasources/{id}/columns` | Describe table structure |
| `oracle_schemas` | `GET /api/datasources/{id}/schemas` | List available schemas |
| `oracle_tables` | `GET /api/datasources/{id}/tables` | List tables in schema |
| `oracle_validate_sql` | `POST /api/tests/control-table/check-sql` | Validate SQL syntax |

### Agent Access Pattern
Agents (GHC, local) can interact with Oracle through the AI router:
```
POST /api/ai/chat
{
  "messages": [...],
  "context": "{ datasource_id: 2, target_table: 'SCHEMA.TABLE' }",
  "provider": "githubcopilot"
}
```

The AI service automatically injects schema context from saved PDMs into the prompt.

## Future: Dedicated MCP Server
For standalone MCP server deployment (compatible with VS Code / IntelliJ MCP clients):
- Server binary: `tools/mcp-oracle-server` (planned)
- Protocol: JSON-RPC over stdio
- Tools: oracle_query, oracle_describe, drd_parse, sql_generate, training_run
