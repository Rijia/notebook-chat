Design a data model using dimensional modeling principles from Ralph Kimball, extended with modern Medallion architecture and Data Vault 2.0 patterns. $ARGUMENTS should describe the business domain and key analytical questions to answer.

## Dimensional Modeling — Kimball Framework

### Core Principle
Design for query performance and business usability, not normalization. The star schema is the contract between engineering and analytics. Every decision must be justified by: does this make the most important queries simpler and faster?

### Step 1: Business Requirements & Grain Declaration
The grain is the single most important modeling decision. Lock it down before writing any schema.

**Requirements Checklist**
- What are the 3–5 most important business questions this model must answer?
- What is the lowest level of detail required? (transaction, session, daily aggregate)
- Who are the consumers? (BI tools, data scientists, ad-hoc SQL, ML pipelines)
- What is the freshness SLA? (real-time, hourly, daily)
- What is the retention policy? (90 days, 3 years, indefinitely)

**Declaring the Grain**
- One row = one [event/transaction/snapshot] per [entity] per [time period]
- Example: "one row = one product sold per order line" — not "one order" (too coarse) and not "one keystroke" (too fine)
- **Never mix grains in a single fact table.** If you need both order-level and line-level, build two fact tables.

### Step 2: Fact Table Design

**Fact Table Types**
| Type | Description | When to Use |
|------|-------------|-------------|
| Transaction | One row per discrete event | Sales, clicks, payments |
| Periodic Snapshot | One row per entity per time period | Daily account balance, weekly inventory |
| Accumulating Snapshot | One row per business process instance, updated over lifecycle | Order fulfillment, loan application stages |

**Fact Table Rules**
- **Only additive or semi-additive measures** belong in fact tables; non-additive facts (ratios, percentages) should NOT be stored — compute them at query time
- Additive: revenue, quantity → can SUM across all dimensions
- Semi-additive: balance, headcount → can SUM across some dimensions but not time (use snapshot instead of SUM)
- Non-additive: margin %, CTR → never store; derive from stored numerator/denominator
- **Store the degenerate dimension** (order number, transaction ID) directly in the fact table as a key, not in a separate dimension
- Use surrogate keys (integer sequences), never natural/business keys, as foreign keys

**Factless Fact Tables**
- Record events with no numeric measure (e.g., "student attended course")
- Used for coverage/existence queries: "which products had no sales this week?"
- Bridge table pattern: resolve many-to-many relationships (one order → multiple promotions applied)

### Step 3: Dimension Table Design

**Dimension Table Rules**
- Denormalized (snowflaking is an anti-pattern for analytical workloads — it forces joins for no query benefit)
- Wide: many descriptive attributes; 50–100+ columns is normal
- Text descriptions, not codes: store "Gold" not "G"; store "Female" not "F"
- **One source of truth per attribute**: if region hierarchy exists in both customer and store dimensions, pick one and reference the other via a conformed dimension

**Slowly Changing Dimensions (SCD)**
| Type | Behavior | Use When |
|------|----------|----------|
| SCD Type 1 | Overwrite old value | History of the attribute is irrelevant |
| SCD Type 2 | Add new row with new surrogate key; set `is_current`, `valid_from`, `valid_to` | Must analyze historical state accurately |
| SCD Type 3 | Add "previous_value" column | Only one prior value matters |
| SCD Type 4 | Separate mini-dimension for rapidly changing attributes | Avoids dimension row explosion for high-cardinality changes |
| SCD Type 6 (hybrid) | SCD2 row + current value column | Need both "what was true then" and "what is true now" in same query |

**SCD Type 2 Template**
```sql
CREATE TABLE dim_customer (
    customer_key        BIGINT PRIMARY KEY,  -- surrogate key
    customer_id         VARCHAR,             -- natural/business key
    customer_name       VARCHAR,
    segment             VARCHAR,
    region              VARCHAR,
    -- SCD2 metadata
    valid_from          DATE NOT NULL,
    valid_to            DATE,                -- NULL means current record
    is_current          BOOLEAN NOT NULL DEFAULT TRUE
);
```
**Critical**: fact table foreign keys must point to `customer_key` (surrogate), never `customer_id`. This preserves the historical snapshot.

**Conformed Dimensions**
- Shared across multiple fact tables (Date, Customer, Product, Geography)
- Enables drill-across queries: joining two fact tables via a shared dimension
- The Date dimension is always conformed; build it once, reuse everywhere
- If two teams define "customer" differently, document it — do not silently merge

**Junk Dimensions**
- Combine low-cardinality flags and indicators (yes/no, status codes) into one table
- Avoids cluttering the fact table with many tiny foreign keys
- Build by taking the Cartesian product of all possible flag combinations

**Role-Playing Dimensions**
- Same physical dimension used with different logical roles in the fact table
- Example: `dim_date` appears as `order_date_key`, `ship_date_key`, `delivery_date_key`
- Implement as views with aliased column names, or as explicit JOIN aliases in queries

### Step 4: Bus Architecture & Integration

**Enterprise Data Warehouse Bus Matrix**
| Business Process | Date | Customer | Product | Store | Employee |
|-----------------|------|----------|---------|-------|----------|
| Sales | ✓ | ✓ | ✓ | ✓ | |
| Returns | ✓ | ✓ | ✓ | ✓ | |
| Inventory | ✓ | | ✓ | ✓ | |
| HR Events | ✓ | | | ✓ | ✓ |

- Conformed dimensions (✓) enable cross-process analysis
- Each row is a fact table; each column is a shared dimension
- Build this matrix before writing any DDL

**Bus Architecture Rules**
- Never model a single business process by creating multiple overlapping fact tables with different grains — pick one grain
- Resist the urge to pre-aggregate: analytics tools and columnar engines handle aggregation efficiently; pre-aggregation sacrifices flexibility
- Aggregate fact tables (daily summaries) are acceptable for performance, but they supplement — never replace — the atomic fact table

### Step 5: Medallion Architecture (Modern Extension)

```
Source Systems → Bronze → Silver → Gold → Consumption
```

**Bronze Layer (Raw / Landing)**
- Exact copy of source data; no transformations
- Schema-on-read; preserve original column names and types
- Append-only or full snapshot; never delete
- Partition by `ingestion_date`
- Purpose: reprocessability — if Silver/Gold logic changes, replay from Bronze

**Silver Layer (Cleaned / Conformed)**
- Deduplicated, nulls handled, types cast, PII masked/tokenized
- Light schema standardization (snake_case columns, UTC timestamps)
- Row-level data quality assertions enforced here (not Bronze, not Gold)
- Corresponds to Kimball's "staging" + normalized ODS layer
- Delta Lake / Iceberg recommended: ACID transactions, schema evolution, time travel

**Gold Layer (Business-Ready / Serving)**
- Kimball-style star schemas, wide flat tables, or aggregated summaries
- Optimized for BI tools, ML feature stores, and self-service analytics
- Separate marts per domain (marketing_mart, finance_mart, product_mart)
- This is where SCD logic, surrogate keys, and conformed dimensions live

**Quality Gates Between Layers**
- Bronze → Silver: completeness (no missing PKs), uniqueness, referential integrity
- Silver → Gold: business rule conformance, metric consistency checks
- Use Great Expectations, dbt tests, or custom SQL assertions; fail the pipeline, don't silently pass bad data

### Step 6: Data Vault 2.0 (Audit-First Alternative)

Use Data Vault when: regulatory audit requirements demand full history, sources are highly volatile, or multiple heterogeneous systems must be integrated without a unified key.

**Core Components**
- **Hub**: unique business key + load timestamp + record source. One hub per business entity.
  ```sql
  CREATE TABLE hub_customer (
      customer_hk      BINARY(16) PRIMARY KEY,  -- SHA-256 of business key
      customer_bk      VARCHAR NOT NULL,         -- business key
      load_dts         TIMESTAMP NOT NULL,
      record_source    VARCHAR NOT NULL
  );
  ```
- **Link**: relationship between hubs (many-to-many by default)
  ```sql
  CREATE TABLE link_order_customer (
      order_customer_hk  BINARY(16) PRIMARY KEY,
      order_hk           BINARY(16) NOT NULL REFERENCES hub_order,
      customer_hk        BINARY(16) NOT NULL REFERENCES hub_customer,
      load_dts           TIMESTAMP NOT NULL,
      record_source      VARCHAR NOT NULL
  );
  ```
- **Satellite**: descriptive attributes + full history (append-only, never update)
  ```sql
  CREATE TABLE sat_customer_crm (
      customer_hk    BINARY(16) NOT NULL REFERENCES hub_customer,
      load_dts       TIMESTAMP NOT NULL,
      load_end_dts   TIMESTAMP,               -- populated by end-dating process
      record_source  VARCHAR NOT NULL,
      hash_diff      BINARY(16),              -- detect row changes
      customer_name  VARCHAR,
      segment        VARCHAR,
      PRIMARY KEY (customer_hk, load_dts)
  );
  ```

**Data Vault vs Kimball Decision Matrix**
| Criterion | Kimball Star Schema | Data Vault 2.0 |
|-----------|--------------------|-|
| Query performance | Excellent | Requires Information Marts (remodel to star) |
| Auditability | Limited (SCD2 tracks one dimension) | Full source traceability on every row |
| Schema flexibility | Requires migration for structural changes | Hubs/Links rarely change; add Satellites freely |
| Implementation complexity | Moderate | High |
| Best for | Analytics-first, stable domains | Regulatory, multi-source integration |

**Recommendation**: Use Data Vault for the integration layer, then build Kimball-style Information Marts (star schemas) on top of it for consumption. The two approaches are complementary.

## Code Standards
- Always show the bus matrix before writing DDL
- For every fact table, explicitly state the grain in a SQL comment
- For every SCD2 dimension, show the `valid_from`, `valid_to`, `is_current` pattern
- Use surrogate keys (BIGINT GENERATED ALWAYS AS IDENTITY or BINARY(16) hash) — never business keys as PKs
- Label each table with its Medallion layer (Bronze/Silver/Gold) in comments or table naming convention (`bronze_`, `silver_`, `gold_`)
- For any non-additive measure, show the correct SQL to derive it (numerator/denominator, never stored ratio)
