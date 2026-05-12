# Guidelines & Best Practices

## DRD Parsing
- Always check all sheets in Excel files; use `_pick_best_drd_sheet()` for auto-detection
- DRD metadata is in rows 1-12 (view name, table name, schema, source, filter criteria)
- Column mappings start after the header row containing "Target Column" or "Attribute Name"

## SQL Generation
- Preserve source table aliases from DRD (multi-word names like `OPN_TAX_LOTS_NONBKR_TGT`)
- Use frequency analysis to detect the primary source alias
- Always qualify column references with table alias
- Handle CASE WHEN expressions spanning multiple lines
- NVL for NULL handling, not COALESCE (Oracle)
- Use `S.` as default source alias only if no better alias detected

## Training Rules
- One rule per (target_table, target_column) – latest wins
- Rule expressions should be complete Oracle SQL expressions
- Include alias references (e.g., `OPN_TAX_LOTS_NONBKR_TGT.COLUMN_NAME`)
- Training wins auto-saved from pipeline comparison grid

## Error Handling
- ORA-01747: Invalid column specification → check alias definitions in FROM/JOIN
- ORA-00904: Invalid identifier → column or alias not found
- Always show error line number + content in the error dialog
- Background validation runs automatically after generation

## UI Patterns
- Rule editor: Use styled modal (not browser prompt)
- Comparison grid: Filter by status, select-all, apply fixes, win/lose tracking
- Coaching: Maintain conversation history, support Enter=send
- All user data must be escaped with `escapeHtml()` before HTML insertion
