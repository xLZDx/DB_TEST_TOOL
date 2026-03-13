# Basic Template Quick Reference

## Template: Basic Mapping Rules (7 columns)

### Column Reference

| # | Column Name | Required | Description | Example |
|---|-------------|----------|-------------|---------|
| 1 | **Rule Name** | ✅ Yes | Descriptive name for the mapping rule | "Customer Name Validation" |
| 2 | **Source Table** | ✅ Yes | Source table (with optional schema) | "public.customers" or "customers" |
| 3 | **Target Table** | ✅ Yes | Target table (with optional schema) | "warehouse.dim_customers" or "dim_customers" |
| 4 | **Transformation SQL Query** | ⚪ Optional | Complete SELECT showing transformation | See examples below |
| 5 | **Filter Condition** | ⚪ Optional | WHERE clause conditions | "status = 'ACTIVE' AND name IS NOT NULL" |
| 6 | **Join Condition** | ⚪ Optional | JOIN conditions if multi-table | "src.location_id = lookup.id" |
| 7 | **Description** | ⚪ Optional | Business logic description | "Validates customer names with location lookup" |

---

## Transformation SQL Query Examples

### Example 1: Simple Column Transformation
```sql
SELECT 
    UPPER(TRIM(customer_name)) as cust_name,
    customer_id,
    email_address
FROM customers
WHERE status = 'ACTIVE'
```

### Example 2: With Lookup/Join
```sql
SELECT 
    c.customer_id,
    UPPER(TRIM(c.customer_name)) as cust_name,
    l.location_name,
    l.region_code
FROM customers c
LEFT JOIN locations l ON c.location_id = l.id
WHERE c.status = 'ACTIVE'
```

### Example 3: With Aggregation
```sql
SELECT 
    customer_id,
    COUNT(*) as order_count,
    SUM(order_amount) as total_amount,
    MAX(order_date) as last_order_date
FROM orders
WHERE order_status = 'COMPLETED'
GROUP BY customer_id
```

### Example 4: Complex Transformation with CASE
```sql
SELECT 
    p.product_id,
    p.product_name,
    CASE 
        WHEN p.price < 10 THEN 'Budget'
        WHEN p.price < 100 THEN 'Standard'
        ELSE 'Premium'
    END as price_category,
    c.category_name,
    COALESCE(p.discount_rate, 0) as discount_rate
FROM products p
INNER JOIN categories c ON p.category_id = c.id
WHERE p.is_active = 1
```

---

## Complete Example Row

| Column | Value |
|--------|-------|
| **Rule Name** | Customer Profile ETL |
| **Source Table** | public.customers |
| **Target Table** | warehouse.dim_customer_profile |
| **Transformation SQL Query** | `SELECT c.customer_id, UPPER(TRIM(c.full_name)) as customer_name, c.email, l.location_name, r.region_name, CASE WHEN c.lifetime_value > 10000 THEN 'VIP' WHEN c.lifetime_value > 1000 THEN 'Premium' ELSE 'Standard' END as customer_tier FROM customers c LEFT JOIN locations l ON c.location_id = l.id LEFT JOIN regions r ON l.region_id = r.id WHERE c.status = 'ACTIVE' AND c.email IS NOT NULL` |
| **Filter Condition** | status = 'ACTIVE' AND email IS NOT NULL AND created_date >= '2020-01-01' |
| **Join Condition** | customers.location_id = locations.id AND locations.region_id = regions.id |
| **Description** | ETL rule for customer profile dimension table. Transforms customer data from operational database to data warehouse, including location and region lookups. Assigns customer tier based on lifetime value. Only includes active customers with valid email addresses created since 2020. |

---

## Schema Handling

### Option 1: Include schema in table name
```
Source Table: public.customers
Target Table: warehouse.dim_customers
```
→ Automatically extracts: `source_schema = "public"`, `source_table = "customers"`

### Option 2: Schema-less (will use default schema)
```
Source Table: customers
Target Table: dim_customers
```
→ Uses default schema from database connection

---

## Important Notes

### After Import - Required Edits
⚠️ **You must edit each imported rule to set correct datasource IDs!**
- Default datasource IDs are set to 1
- Update `source_datasource_id` to your actual source database
- Update `target_datasource_id` to your actual target database

### Best Practices
1. **Use descriptive rule names** - helps identify rules later
2. **Include complete SQL in Transformation SQL Query** - documents full transformation logic
3. **Add schema prefixes** to table names when working with multiple schemas
4. **Write clear descriptions** - explain the business purpose
5. **Test with small datasets first** - verify transformations work correctly

### Filter vs Join Conditions
- **Filter Condition**: WHERE clause filters applied to source data
- **Join Condition**: How to join multiple tables in validation query
- **Transformation SQL Query**: Can include both filters and joins in complete SELECT statement

### When to Use Each Field

Use **Transformation SQL Query** when:
- You have complex column transformations
- You need to show complete data flow
- Multiple tables are involved with JOINs
- You want to document the exact transformation logic

Use **Filter Condition** when:
- You have simple row-level filters
- You want to highlight specific filtering logic
- Filters are simple enough to separate from main query

Use **Join Condition** when:
- You need to specify join logic separately
- Tests will join source and target for comparison
- You want to highlight table relationships

---

## Template Type Detection

The system will automatically detect your template type based on column headers:
- If headers match Basic template → Auto-detects as Basic
- Works with: exact match, case-insensitive, with/without whitespace
- Minimum required headers: Rule Name, Source Table, Target Table

---

## Download & Import Steps

### Download
1. Navigate to **Mappings** page
2. Click **"Download Templates"** button (green button at top)
3. Select **"Basic Mapping Rules"** from the list
4. Click **"Download"** button
5. Excel file downloads as `mapping_template_basic.xlsx`

### Fill Out
1. Open Excel file
2. See **"Documentation"** sheet for detailed instructions
3. Fill out **"Mapping Rules"** sheet with your data
4. Required columns: Rule Name, Source Table, Target Table
5. Save your file

### Import
1. Click **"Import from Excel"** button on Mappings page
2. Select your filled Excel file
3. Choose template type: **"Auto-detect"** (recommended) or **"basic"**
4. Click **"Import"**
5. Review import results (success/error counts)

### Edit After Import
1. Click **"Edit"** button (pencil icon) on any imported rule
2. Update **Source Datasource ID** to correct database
3. Update **Target Datasource ID** to correct database
4. Review and adjust other fields as needed
5. Click **"Save"**

### Generate Tests
1. Select rules you want to test (checkboxes)
2. Choose **Test Connection** from dropdown
3. Click **"Generate Tests from Selected Rules"**
4. Tests are created and ready to run

---

## Troubleshooting

### Auto-detection not working?
- Check that your Excel file has headers in the first row
- Ensure headers match expected names (case-insensitive)
- Minimum headers: "Rule Name", "Source Table", "Target Table"
- Try selecting template type manually instead of auto-detect

### Download not working?
- Check that server is running (http://127.0.0.1:8550)
- Clear browser cache and try again
- Check browser console for JavaScript errors
- Templates are in `data/mapping_template_*.xlsx` files

### Import errors?
- Validate required fields are filled: Rule Name, Source Table, Target Table
- Check for special characters in table names
- Ensure SQL syntax is valid in Transformation SQL Query field
- Review error messages for specific row issues

---

## Template Comparison

| Feature | OLD Basic (14 cols) | NEW Basic (7 cols) |
|---------|---------------------|-------------------|
| Columns | 14 | 7 (50% reduction) |
| Required Fields | 5 | 3 |
| Datasource IDs | Manual entry | Auto-defaults to 1 |
| Schema | Separate column | Included in table name |
| Source/Target Columns | Separate columns | Extracted from SQL |
| Transformation Logic | Simple expression | Complete SQL SELECT |
| Complexity | High | Low |
| Time to Fill | ~5 min/rule | ~2 min/rule |

---

**Recommendation**: Use the **NEW simplified Basic template** for most common scenarios. Use Enterprise, Data Warehouse, or ETL Pipeline templates only when you need their specific advanced features.
