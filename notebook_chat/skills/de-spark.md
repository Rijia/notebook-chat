Optimize PySpark and Spark SQL code for performance, cost, and correctness. $ARGUMENTS should describe the job or query to optimize, or ask for a design review. Reference framework: Holden Karau & Rachel Warren, *High Performance Spark* (O'Reilly).

## Core Mental Model: Where Time Goes

Before tuning anything, profile first. Blind optimization is expensive and often counterproductive.

```python
# Always start with: what is actually slow?
spark.sparkContext.setLogLevel("WARN")

# Enable Spark UI and read the DAG before touching code
# Key questions from the Spark UI:
# 1. Which stage takes the most time?
# 2. Is there a shuffle? How many bytes?
# 3. Are tasks evenly distributed, or is there skew?
# 4. How much spill to disk?
```

**Performance Hierarchy** (fix in this order)
1. Data skew → tasks hang while one partition takes 100× longer than others
2. Excessive shuffle → GBs moved across the network for a join or groupBy
3. Wrong join strategy → sort-merge join when broadcast join was possible
4. Missing predicate pushdown → reading 100GB when 1GB was needed
5. UDF overhead → Python serialization when a native Spark function exists
6. Misconfigured resources → too few executors, wrong partition count

---

## 1. Adaptive Query Execution (AQE)

AQE (Spark 3.0+) automatically adjusts query plans at runtime. Enable it; it handles most shuffle partition tuning automatically.

```python
spark.conf.set("spark.sql.adaptive.enabled", "true")                          # default true in Spark 3.2+
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")       # merge small post-shuffle partitions
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")                 # split skewed partitions automatically
spark.conf.set("spark.sql.adaptive.localShuffleReader.enabled", "true")       # avoid network fetch for map-side data

# AQE will dynamically change partition count after shuffle based on actual data size
# Still set a reasonable upper bound:
spark.conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "64mb")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128mb")
```

**When AQE is not enough**: AQE sees runtime statistics but cannot fix structural problems in your code (wrong join order, missing filters, bad data layout). Use it as a safety net, not a substitute for thinking.

---

## 2. Shuffle Optimization

Shuffle is the single biggest source of Spark performance problems. Every `groupBy`, `join`, `distinct`, `repartition`, and `window` function with non-adjacent partitions triggers a shuffle.

**Partition Sizing Rules**
- Target: 100–200 MB per partition after shuffle (128 MB is a common sweet spot)
- Formula: `num_partitions = total_shuffle_data_bytes / target_partition_bytes`
- `spark.sql.shuffle.partitions` default is 200 — almost always wrong for your data size
  ```python
  # For a 50 GB shuffle into 128 MB partitions:
  spark.conf.set("spark.sql.shuffle.partitions", str(50 * 1024 // 128))  # ≈ 400
  ```

**Repartition vs Coalesce**
| Operation | Triggers Shuffle | Use When |
|-----------|-----------------|----------|
| `repartition(n)` | Yes | Increasing partition count OR redistributing evenly |
| `repartition(n, col)` | Yes | Pre-partitioning by join/groupBy key to co-locate data |
| `coalesce(n)` | No (narrow) | Only reducing partition count; avoids unnecessary shuffle |

```python
# Pre-partition before a join on the same key → eliminates join shuffle
df_orders = df_orders.repartition(400, "customer_id")
df_customers = df_customers.repartition(400, "customer_id")
result = df_orders.join(df_customers, "customer_id")  # no shuffle needed
```

**Minimizing Shuffle Data Volume**
- Filter and project BEFORE joins: reduce data before the shuffle, not after
- Drop unnecessary columns before `groupBy` / `join`
- Use `reduceByKey` over `groupByKey` in RDD API: combines locally before shuffle

```python
# BAD: shuffles all values, then reduces
rdd.groupByKey().mapValues(sum)

# GOOD: reduces locally first (map-side combine), then shuffles partial sums
rdd.reduceByKey(lambda a, b: a + b)
```

---

## 3. Join Strategies

Choose the right join strategy explicitly. Spark's optimizer makes good choices most of the time, but for large or skewed datasets, hints are faster than waiting for statistics.

**Join Strategy Decision Tree**
```
Is one side small enough to broadcast (< spark.sql.autoBroadcastJoinThreshold)?
  YES → Broadcast Hash Join (BHJ): fastest, no shuffle
  NO  → Is the join key sortable and data already sorted/partitioned?
    YES → Sort-Merge Join (SMJ): standard for large-large joins
    NO  → Shuffle Hash Join (SHJ): builds hash table; faster than SMJ if build side fits in memory
          ⚠️ Can OOM if build side is larger than estimated
```

**Broadcast Hash Join (BHJ)**
```python
from pyspark.sql.functions import broadcast

# Explicit broadcast hint (overrides autoBroadcastJoinThreshold)
result = df_large.join(broadcast(df_small), "key")

# Tune the auto-broadcast threshold (default 10MB — often too conservative)
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(50 * 1024 * 1024))  # 50MB
```
- Sends the small table to every executor; no shuffle of the large table
- Effective up to ~200–500 MB depending on executor memory
- Do NOT broadcast if the small side is modified frequently (broadcast is computed once)

**Sort-Merge Join Optimization**
```python
# Hint syntax (Spark 3.0+)
df_a.hint("MERGE").join(df_b, "key")

# If both sides are already bucketed on the same key with the same bucket count
# → SMJ skips the sort phase entirely (no exchange needed)
```

**Skew Join**
```python
# AQE handles this automatically if skewJoin.enabled = true
# For manual control, salting:
import pyspark.sql.functions as F

SALT = 10
df_skewed = df_skewed.withColumn("salt", (F.rand() * SALT).cast("int"))
df_small = df_small.withColumn("salt", F.explode(F.array([F.lit(i) for i in range(SALT)])))
result = df_skewed.join(df_small, ["key", "salt"]).drop("salt")
```

---

## 4. Predicate Pushdown & Projection Pushdown

Columnar formats (Parquet, ORC, Delta) can skip entire row groups and columns before data reaches Spark. This is the cheapest optimization: don't read data you don't need.

**Predicate Pushdown**
```python
# Spark pushes WHERE filters to the data source automatically — but only for supported predicates
# Always filter on partition columns first
df = spark.read.parquet("s3://bucket/events/")
result = df.filter("event_date = '2024-01-15'")  # partition pruning: reads only one partition folder
result = df.filter("event_date BETWEEN '2024-01-01' AND '2024-01-31'")  # reads 31 folders

# Verify pushdown happened: look for "PushedFilters" in the plan
result.explain(extended=True)
# Look for: PushedFilters: [IsNotNull(user_id), EqualTo(status,active)]
```

**Projection Pushdown**
```python
# Select only needed columns before any transformation — columnar engines skip unneeded columns at read time
df = spark.read.parquet("s3://bucket/wide_table/")
df = df.select("user_id", "event_type", "event_ts")  # do this FIRST
result = df.filter(...).groupBy(...)
```

**Partitioning Strategy for Files**
- Partition by columns used in WHERE filters: `event_date`, `country`, `event_type`
- Avoid over-partitioning: if a partition has < 128 MB, it's too granular (too many small files)
- Avoid under-partitioning: if a partition has > 1 GB, filters within it are slow
- `Z-ordering` (Delta Lake): colocates correlated columns within Parquet files for multi-dimensional filtering

```python
# Delta Lake Z-order (optimizes for multi-column filter pushdown within partitions)
spark.sql("OPTIMIZE delta.`/path/to/table` ZORDER BY (user_id, event_type)")
```

---

## 5. UDF Anti-Patterns and Alternatives

Python UDFs are the most common source of unnecessary overhead. Each row crosses the Python–JVM boundary twice (serialize → Python → deserialize).

**Performance Cost of UDFs**
| Method | Serialization | Performance |
|--------|--------------|-------------|
| Native Spark SQL / DataFrame API | None | Fastest |
| Pandas UDF (vectorized, via Arrow) | Arrow (columnar batch) | 5–10× faster than row UDF |
| Row-level Python UDF | Pickle per row | Slowest; avoid for large datasets |
| Scala/Java UDF registered in PySpark | None (runs on JVM) | Same as native |

```python
# BAD: row-level Python UDF
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

@udf(returnType=StringType())
def clean_email(email):
    return email.strip().lower() if email else None

df = df.withColumn("email", clean_email("email"))

# GOOD: use native Spark functions
import pyspark.sql.functions as F
df = df.withColumn("email", F.lower(F.trim(F.col("email"))))

# GOOD: Pandas UDF (vectorized) when native functions are insufficient
from pyspark.sql.functions import pandas_udf
import pandas as pd

@pandas_udf(returnType=StringType())
def complex_transform(series: pd.Series) -> pd.Series:
    return series.str.extract(r'(\w+@\w+\.\w+)')[0]

df = df.withColumn("email_clean", complex_transform("raw_email"))
```

**When a UDF is Unavoidable**
- Complex business logic with no native equivalent
- External library calls (NLP models, geo libraries)
- In these cases, use Pandas UDF (Arrow-based) and batch as much computation as possible per call

---

## 6. Memory Management & Spill

Spill to disk means executor memory was exhausted during shuffle/sort. It doesn't fail — but it's 10–100× slower than in-memory operations.

**Identifying Spill**
- Spark UI → Stage → "Shuffle Spill (Memory)" and "Shuffle Spill (Disk)" columns
- If spill > 0, you need more memory per executor OR fewer/smaller tasks

**Executor Memory Configuration**
```python
# Total executor memory split:
# spark.executor.memory = JVM heap (for task execution, shuffle, aggregation)
# spark.executor.memoryOverhead = off-heap (for Python process, Arrow buffers, OS overhead)

# Rule of thumb: overhead = max(384MB, 0.10 × executor.memory)
# For PySpark jobs with Pandas UDFs, increase overhead to 20–30% of executor.memory

spark.conf.set("spark.executor.memory", "8g")
spark.conf.set("spark.executor.memoryOverhead", "2g")  # 20% for PySpark

# Memory fractions:
spark.conf.set("spark.memory.fraction", "0.6")        # fraction of heap for execution + storage
spark.conf.set("spark.memory.storageFraction", "0.5") # within that, fraction reserved for caching
```

**Caching Strategy**
```python
# Cache ONLY when a DataFrame is used multiple times in different branches
# Caching has a cost: serialization + memory pressure

df.cache()          # MEMORY_AND_DISK: spills to disk if needed (safer default)
df.persist(StorageLevel.MEMORY_ONLY)    # OOM if data is too large
df.persist(StorageLevel.DISK_ONLY)      # for data too large to fit in memory at all

# Always unpersist when done
df.unpersist()

# Anti-pattern: caching inside a loop or a DataFrame used only once
```

---

## 7. Small Files Problem

Thousands of small Parquet files (< 10 MB) cause massive overhead: S3 list operations, per-file metadata reads, too many tasks.

```python
# Detect the problem
df = spark.read.parquet("s3://bucket/table/")
print(df.rdd.getNumPartitions())  # if > 10× expected, you have small files

# Fix at write time: coalesce before writing
df.coalesce(200).write.parquet("s3://output/")  # for batch jobs

# Fix with Delta Lake OPTIMIZE (compacts small files without rewriting table)
spark.sql("OPTIMIZE delta.`/path/to/table`")

# Fix with repartition (use when you also need to redistribute by key)
df.repartition(200, "date").write.partitionBy("date").parquet("s3://output/")
```

---

## 8. Structured Streaming

**Watermarking (late data handling)**
```python
from pyspark.sql.functions import window, col

result = (
    df
    .withWatermark("event_time", "10 minutes")  # tolerate up to 10min late data
    .groupBy(window(col("event_time"), "5 minutes"), col("user_id"))
    .agg(F.count("*").alias("event_count"))
)
```

**Trigger Modes**
```python
# Micro-batch (default): process all available data, then wait
query = result.writeStream.trigger(processingTime="1 minute").start()

# Available-now (batch-like): process all backlog, then stop — use for scheduled jobs
query = result.writeStream.trigger(availableNow=True).start()

# Continuous (experimental): ~1ms latency, limited operator support
query = result.writeStream.trigger(continuous="1 second").start()
```

**Checkpointing (mandatory for production)**
```python
query = (
    result.writeStream
    .outputMode("append")
    .option("checkpointLocation", "s3://bucket/checkpoints/my_job/")
    .trigger(processingTime="5 minutes")
    .start("s3://bucket/output/")
)
```

---

## Optimization Checklist

Before submitting any Spark job to production:

| Check | Question |
|-------|----------|
| AQE enabled | Is `spark.sql.adaptive.enabled = true`? |
| Shuffle partitions | Is partition count set based on actual data size, not the 200 default? |
| Join strategy | Is broadcast used where applicable? Are large-large joins pre-partitioned? |
| Predicate pushdown | Are filters on partition columns applied before any transformation? |
| Projection pushdown | Are only needed columns selected at read time? |
| UDFs | Is every UDF replaceable with a native function? If not, is it a Pandas UDF? |
| Spill | Does the Spark UI show zero spill for shuffle stages? |
| Small files | Are output file sizes in the 128–512 MB range? |
| Caching | Is cache/persist used only for DataFrames with multiple downstream consumers? |
| Partitioning strategy | Is the output partitioned by the columns most commonly used in downstream filters? |

## Code Standards
- Always run `.explain(extended=True)` on complex queries and verify `PushedFilters` and `PartitionFilters` appear
- Report partition count, shuffle bytes, and spill from Spark UI when benchmarking optimization changes
- Show before/after runtime and stage metrics for every optimization — never claim improvement without measurement
- Default to Pandas UDFs over row-level UDFs; default to native functions over any UDF
