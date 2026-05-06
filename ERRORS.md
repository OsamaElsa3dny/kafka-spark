# Kafka + Spark Streaming — Error Log & Fixes

This document explains every error encountered during setup, why it happened, and how it was fixed.

---

## Table of Contents

1. [Error 1: `Failed to find data source: kafka`](#error-1-failed-to-find-data-source-kafka)
2. [Error 2: `Column 'json_value' does not exist`](#error-2-column-json_value-does-not-exist)
3. [Error 3: `Connection refused` / Cannot connect to `kafka:9092`](#error-3-connection-refused--cannot-connect-to-kafka9092)
4. [Why `docker-compose.yml` was edited](#why-docker-composeyml-was-edited)
5. [Why `requirements.txt` was created](#why-requirementstxt-was-created)
6. [Why `.gitignore` was created](#why-gitignore-was-created)
7. [First-time Spark delay explained](#first-time-spark-delay-explained)

---

## Error 1: `Failed to find data source: kafka`

### The Error Message
```
pyspark.errors.exceptions.captured.AnalysisException:
Failed to find data source: kafka.
Please deploy the application as per the deployment section of
Structured Streaming + Kafka Integration Guide.
```

### Why It Happens
Apache Spark does **not** include the Kafka connector in its default installation.
When you call:
```python
spark.readStream.format("kafka")...
```
Spark looks for a class called `org.apache.spark.sql.kafka010.KafkaSourceProvider`.
If that class is not found on the classpath, Spark throws this error.

Think of it like trying to open a `.zip` file without having WinRAR installed —
the tool simply doesn't know how to handle that format.

### The Fix
Add the Kafka connector package to the SparkSession configuration:
```python
spark = SparkSession.builder \
    .appName("KafkaSparkOrderWorkshop") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.1") \
    .getOrCreate()
```

This tells Spark to download the JAR from the Maven Central repository automatically.

### Important Note
The package version **must match** your Spark version:
- Spark 4.x uses Scala 2.13 → `spark-sql-kafka-0-10_2.13:4.1.1`
- Spark 3.x uses Scala 2.12 → `spark-sql-kafka-0-10_2.12:3.x.x`

---

## Error 2: `Column 'json_value' does not exist`

### The Error Message (implied)
```
AnalysisException: Column 'json_value' does not exist
```

### Why It Happens
The original `spark_consumer.py` had a redundant/duplicate line:

```python
# Line 14 - extracts JSON fields correctly
json_df = raw_df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")
# At this point json_df already has columns: customer, product, price

# Line 15 - tries to do it AGAIN on a non-existent column
orders_df = json_df.select(from_json(col("json_value"), schema).alias("data")).select("data.*")
```

After line 14, `json_df` already contains the parsed columns.
There is **no column named `json_value`** anywhere in the DataFrame.
So line 15 crashes.

### The Fix
Remove the redundant line and use `json_df` directly:
```python
# Before (broken)
json_df = raw_df.selectExpr("CAST(value AS STRING)").select(from_json(col("value"), schema).alias("data")).select("data.*")
orders_df = json_df.select(from_json(col("json_value"), schema).alias("data")).select("data.*")  # <-- BROKEN

# After (fixed)
json_df = raw_df.selectExpr("CAST(value AS STRING)").select(from_json(col("value"), schema).alias("data")).select("data.*")
# Use json_df directly
target_df = json_df.withColumn("discounted_price", col("price") * 0.9)
```

---

## Error 3: `Connection refused` / Cannot connect to `kafka:9092`

### Why It Happens
The original code used `kafka:9092` as the Kafka broker address:
```python
bootstrap_servers='kafka:9092'       # producer_orders.py
kafka.bootstrap.servers=kafka:9092   # spark_consumer.py
```

However, `kafka` is a **Docker-internal hostname**.
It only exists **inside** the Docker network created by `docker-compose`.
When you run Python scripts from your **host machine** (outside Docker), the hostname `kafka` cannot be resolved.

The result is a connection timeout or "Connection refused" error because your computer doesn't know what `kafka` is.

### The Fix
Change all broker addresses from `kafka:9092` to `localhost:9092`:
```python
bootstrap_servers='localhost:9092'       # producer_orders.py
kafka.bootstrap.servers=localhost:9092   # spark_consumer.py
```

`localhost:9092` is the port exposed by Docker to your host machine.

---

## Why `docker-compose.yml` was edited

### Original Setting
```yaml
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
```

### Problem
Kafka tells its clients (producers and consumers) to connect using the address specified in `KAFKA_ADVERTISED_LISTENERS`.
When a client connects and asks "Where is the leader broker?", Kafka replies with this address.

If Kafka says "connect to `kafka:9092`", external clients (running outside Docker) will fail because they can't resolve that hostname.

### The Fix
```yaml
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
```

Now Kafka tells clients to connect to `localhost:9092`, which is accessible from your host machine because Docker maps the container's port 9092 to your machine's port 9092 via:
```yaml
ports:
  - "9092:9092"
```

### Note
If your producer/consumer ran **inside** a Docker container on the same network, `kafka:9092` would work fine.
But since we run them from the **host**, we need `localhost:9092`.

---

## Why `requirements.txt` was created

### Purpose
`requirements.txt` lists all Python dependencies your project needs.

### Content
```
kafka-python>=2.0.0
pyspark>=4.1.0
```

### Benefits
1. **Reproducibility**: Anyone can recreate the exact environment with:
   ```bash
   pip install -r requirements.txt
   ```
2. **Version Control**: You can see exactly which versions were used
3. **CI/CD**: Automated testing and deployment systems read this file
4. **Sharing**: When sharing the project, you don't need to share the `venv/` folder (which is huge), just this small text file

---

## Why `.gitignore` was created

### Purpose
`.gitignore` tells Git which files/folders to ignore and never commit.

### Content
```gitignore
# Python virtual environment
venv/

# Python cache
__pycache__/
*.pyc
*.pyo

# Environment files
.env
```

### Why Each Entry

| Entry | Why Ignore It |
|-------|--------------|
| `venv/` | Contains thousands of files (100+ MB). These are machine-specific and can be recreated with `pip install -r requirements.txt` |
| `__pycache__/` | Auto-generated by Python when it compiles `.py` files. Not needed in version control |
| `*.pyc`, `*.pyo` | Compiled Python bytecode files. Also auto-generated |
| `.env` | Usually contains secrets like API keys, passwords. Should never be committed |

### What You SHOULD Commit
- `producer_orders.py`
- `spark_consumer.py`
- `docker-compose.yml`
- `requirements.txt`
- `.gitignore`
- This file (`ERRORS.md`)

---

## First-Time Spark Delay Explained

### What Happens
The first time you run `spark_consumer.py`, you will see output like this:
```
downloading https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client-runtime/3.4.2/hadoop-client-runtime-3.4.2.jar ...
```

It takes 1-3 minutes and appears to "hang".

### Why It Happens
Spark is downloading the Kafka connector JAR and its dependencies (~60 MB) from Maven Central.

### Is It Normal?
**Yes, completely normal.** This only happens:
- The **first time** you run the script
- If you delete the `~/.ivy2` cache directory

### Subsequent Runs
After the first run, Spark caches the JARs in `~/.ivy2/cache/`. Future runs start immediately.

---

## Quick Reference: How to Run the Project

```bash
# 1. Start Kafka (Terminal 1)
docker compose up -d

# 2. Activate virtual environment (all terminals)
source venv/bin/activate

# 3. Start Spark Consumer (Terminal 2) - runs forever
python spark_consumer.py

# 4. Run Producer (Terminal 3) - sends 6 orders
python producer_orders.py

# 5. Stop everything
# Press Ctrl+C in Terminal 2 (Spark consumer)
# Then:
docker compose down
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│               Host Machine                   │
│  ┌───────────┐      ┌──────────────────┐   │
│  │ Producer  │      │ Spark Consumer   │   │
│  │ (Python)  │      │ (PySpark)        │   │
│  └─────┬─────┘      └────────┬─────────┘   │
│        │                      │             │
│        │  localhost:9092      │ localhost:9092
│        │                      │             │
│  ┌─────┴──────────────────────┴─────────┐  │
│  │     Docker Container: kafka          │  │
│  │     port 9092 → host:9092            │  │
│  └──────────────────────────────────────┘  │
│                │                             │
│                │ zookeeper:2181              │
│                ▼                             │
│  ┌──────────────────────────────────────┐  │
│  │     Docker Container: zookeeper      │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```
