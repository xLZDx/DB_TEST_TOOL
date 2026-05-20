# Agents

## Available Agents

### SQL Developer (Default)
- **Role**: Oracle SQL generation, DRD-to-INSERT mapping, expression debugging
- **Provider**: GitHub Copilot (GHC)
- **Capabilities**: Generate INSERT/MERGE SQL, resolve alias mismatches, suggest JOINs, fix ORA errors
- **Used by**: Control Table modal, Training Studio coaching, Training Pipeline

### DRD Parser
- **Role**: Parse DRD Excel/CSV files, extract column mappings, detect metadata
- **Provider**: Built-in (no AI needed for basic parsing; AI for ambiguous mappings)
- **Capabilities**: Multi-sheet detection, metadata extraction (view_name, source_schema, filter_criteria), column-to-expression mapping
- **Used by**: DRD upload flow, Control Table Step 1

### SQL Validator
- **Role**: Validate generated SQL against live Oracle database
- **Provider**: Built-in (SQLAlchemy + cx_Oracle)
- **Capabilities**: Syntax check, alias resolution, NOT NULL risk detection, datatype mismatch detection, auto-fix suggestions
- **Used by**: Background validation, Check SQL button, Training Pipeline

### Training Orchestrator
- **Role**: Run iterative training pipeline, compare generated vs expected, persist wins
- **Provider**: GHC + local rules engine
- **Capabilities**: Column-level comparison, iterative refinement (up to 10 rounds), rule persistence, win/lose tracking
- **Used by**: Training Studio, Automation Loop

## Agent Configuration

Agents are managed through the `/api/ai/agents` endpoint:
```
GET  /api/ai/agents              # List all agents
POST /api/ai/agents              # Create agent
PUT  /api/ai/agents/{id}         # Update agent
```

Each agent has:
- `name`: Display name (e.g., "SQL/PLSQL Developer")
- `role`: Agent role description
- `provider`: "githubcopilot" or "local"
- `system_prompt`: Custom system prompt for the agent
- `tools`: List of allowed MCP tools

## Creating Custom Agents

To add a new agent for a specific task:
1. Go to Settings → Agents
2. Click "Add Agent"
3. Set name, role, and system prompt
4. Select provider (GHC recommended for SQL tasks)
5. Optionally restrict available tools
