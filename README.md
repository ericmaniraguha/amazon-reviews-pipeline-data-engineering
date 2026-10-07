# Amazon Reviews Data Engineering Pipeline

A production-grade batch data engineering pipeline that ingests, stores, and analyses 694K+ Amazon Beauty product reviews using **ClickHouse** and **Python**.

Built as part of the **Senior Data Engineer technical assessment** for the National Bank of Rwanda (BNR).

---

## Architecture

```
JSONL Dataset
     │
     ▼
ingest_review_data.py          ← concurrent multi-threaded ingestion
     │  (ThreadPoolExecutor)
     ▼
ClickHouse (Docker)            ← ReplacingMergeTree for deduplication
     │  amazon.reviews
     ▼
visualize_review_data.py       ← SQL analytics via HTTP API + Polars
     │
     ▼
results/                       ← PNGs, CSVs, summary report
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Database | ClickHouse 25.x (Dockerized) |
| Processing | Python 3.10 + Polars DataFrames |
| Ingestion | concurrent.futures (ThreadPoolExecutor) |
| Analytics | ClickHouse SQL + Polars |
| Visualisation | Matplotlib + Seaborn |
| Infrastructure | Docker Compose |

---

## Project Structure

```
.
├── src/
│   ├── ingest_review_data.py      # Concurrent batch ingestion pipeline
│   └── visualize_review_data.py   # Analytics queries + visualisations
├── sql/
│   └── schema.sql                 # ClickHouse DDL + analytical queries
├── results/                       # Generated outputs (PNGs, CSVs, report)
├── data/                          # Dataset directory (not tracked in git)
├── docker-compose.yml             # ClickHouse container configuration
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
└── Final-report.md                # Full technical report
```

---

## Quick Start

### Prerequisites

- Docker 20.10+ with Docker Compose
- Python 3.10+
- 10GB+ free disk space (dataset ~1.8GB uncompressed)

### 1. Clone and configure

```bash
git clone <repo-url>
cd amazon-reviews-de-pipeline

cp .env.example .env
# Edit .env and set your preferred password
```

### 2. Start ClickHouse

```bash
docker-compose up -d
docker ps   # verify clickhouse-server is running
```

> **Note:** `docker-compose.yml` maps host port **80 → container 8123** (HTTP) and **9000 → 9000** (native).  
> On a local machine without root, change `"80:8123"` to `"8123:8123"` in `docker-compose.yml` and update `CLICKHOUSE_PORT = 8123` in `src/visualize_review_data.py`.

### 3. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install the custom ClickHouse dbutils library
git clone https://github.com/datasciencenbr/python-dbutils.git
cd python-dbutils && pip install . && cd ..

pip install -r requirements.txt
```

### 4. Download the dataset

```bash
mkdir -p data/
# Linux/macOS
wget https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/All_Beauty.jsonl.gz
gunzip All_Beauty.jsonl.gz
mv All_Beauty.jsonl data/

# Windows (PowerShell)
# Invoke-WebRequest -Uri "https://mcauleylab.ucsd.edu/..." -OutFile "data\All_Beauty.jsonl.gz"
# Then extract with 7-Zip or similar
```

### 5. Create the schema

```bash
docker exec -it clickhouse-server clickhouse-client \
    -u analytic --password your_password_here \
    --queries-file /dev/stdin < sql/schema.sql
```

### 6. Run the ingestion pipeline

```bash
python3 src/ingest_review_data.py data/All_Beauty.jsonl

# Monitor progress
tail -f ingestion.log
```

### 7. Run analytics and generate visualisations

```bash
python3 src/visualize_review_data.py
```

Outputs are written to the working directory: `rating_analysis.png`, `top_products.csv`, `user_behavior.csv`, `temporal_analysis.csv`, `analysis_summary.txt`.

---

## Key Results

| Metric | Value |
|---|---|
| Total reviews processed | 694,252 |
| Unique customers | 631,986 |
| Unique products | 115,709 |
| Average rating | 3.96 / 5.0 |
| Verified purchases | 90.4% |
| Processing throughput | 1,000+ records/second |
| Duplicate records | 0 (ReplacingMergeTree) |

### Rating Distribution

| Stars | Count | % of Total |
|---|---|---|
| ★★★★★ | 416,435 | 60.0% |
| ★★★★ | 78,608 | 11.3% |
| ★★★ | 55,720 | 8.0% |
| ★★ | 42,601 | 6.1% |
| ★ | 100,888 | 14.5% |

### Screenshots

| Screenshot | Description |
|---|---|
| [Schema created](results/Schema%20created%20-%20Table%20is%20Empty.png) | ClickHouse table before ingestion |
| [Ingestion logs](results/ingestion-logs.jpg) | Real-time pipeline progress |
| [Data inserted](results/data_inserted_in_db.png) | Post-ingestion database state |
| [Dataset overview](results/dataset_overview.png) | Terminal stats after load |
| [Rating analysis](results/rating_analysis.png) | 4-panel rating visualisation |
| [Top products](results/rating_distribution_%26_top_products.png) | Product performance chart |
| [User behaviour](results/user-behavior-analysis.png) | Power user analytics |

---

## Database Schema

```sql
CREATE TABLE amazon.reviews (
    review_id         String,      -- Composite: user_id + asin + timestamp
    user_id           String,
    asin              String,      -- Amazon Standard Identification Number
    parent_asin       String,
    rating            Int32,
    title             String,
    text              String,
    images            String,      -- JSON-encoded
    helpful_vote      Int32,
    verified_purchase UInt8,
    timestamp         Int64
)
ENGINE = ReplacingMergeTree
PRIMARY KEY review_id
ORDER BY (asin, timestamp);
```

See [sql/schema.sql](sql/schema.sql) for the full DDL and analytical query library.

---

## Pipeline Design Decisions

**ReplacingMergeTree** — chosen over MergeTree to handle duplicate records that arise from retrying failed batch inserts. ClickHouse deduplicates during background merges; `FINAL` keyword forces immediate deduplication at query time.

**Composite review_id** (`user_id + asin + timestamp`) — a customer cannot review the same product twice at the exact same millisecond, making this combination a reliable natural key.

**ThreadPoolExecutor for ingestion** — overlaps I/O wait times between batch reads and database writes, achieving 1,000+ records/second on a single machine.

**Polars over Pandas** — zero-copy Arrow memory model reduces peak memory footprint during batch DataFrame construction.

---

## Future Improvements

- Apache Airflow DAG for scheduled / triggered re-ingestion
- Kafka integration for real-time streaming
- dbt models for analytics layer
- Grafana dashboard over ClickHouse HTTP connector
- Great Expectations for schema validation at ingest time

---

## Author

**Eric Maniraguha** — [ericmaniraguha@gmail.com](mailto:ericmaniraguha@gmail.com)
# amazon-reviews-pipeline-data-engineering
