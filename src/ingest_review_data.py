
# Data ingestion --> processes and loads Amazon Beauty product reviews into a ClickHouse database.

# Imports all necessary modules for JSON handling, logging, multithreading, environment config, 
# database interaction, DataFrame operations, and CLI argument parsing.

import json
import logging
from concurrent.futures import ThreadPoolExecutor # for parallel processing
from decouple import AutoConfig
from dbutils import Query
import polars as pl
import argparse


# Sets up logging to write messages into ingestion.log. Records timestamps, log level (INFO/ERROR), and message text.

logging.basicConfig(
    filename="ingestion.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Loads configuration from environment variables or .env file.
config = AutoConfig(search_path=".")

HOST = config("db_clickhouse_host")
PORT = config("db_clickhouse_port", cast=int)
USER = config("db_clickhouse_user")
PASSWORD = config("db_clickhouse_pass")
DB = config("db_clickhouse_db")

SCHEMA = config("clickhouse_schema")
TABLE = config("clickhouse_table")
BATCH_SIZE = config("batch_size", cast=int, default=500) # Number of records to process in each batch
MAX_WORKERS = config("max_workers", cast=int, default=4) # Number of threads for parallel processing
MAX_CHUNK = config("max_chunk", cast=int, default=500) # Number of rows per insert chunk or Maximum chunk size per write operation.

# Initializes ClickHouse connection using dbutils.
clickhouse = Query(
    db_type="clickhouse",
    db=DB,
    db_host=HOST,
    db_port=PORT,
    db_user=USER,
    db_pass=PASSWORD,
)

# Function to insert a batch of records into ClickHouse.
def insert_batch(batch):
    try:
        rows = []
        # Processes each record in the batch to prepare it for insertion.
        for record in batch:
            # Create a unique review_id by combining user_id, asin, and timestamp
            review_id = f"{record.get('user_id', '')}_{record.get('asin', '')}_{record.get('timestamp', 0)}"

            # Ensure images is always a list of strings
            images = record.get("images", [])
            if isinstance(images, dict): # if it's a dict, convert to JSON string and wrap in list
                images = [json.dumps(images)]  # serialize dict as string
            elif isinstance(images, str): # if it's a single string, wrap in list
                images = [images]
            elif isinstance(images, list): # if it's already a list
                # stringify any non-string elements
                images = [str(img) for img in images] # ensure all elements are strings
            else:
                images = [] # default to empty list if images is None or unexpected type

#
            row = {
                "review_id": review_id,
                "user_id": str(record.get("user_id", "")), # ensure user_id is a string
                "asin": str(record.get("asin", "")), # ensure asin is a string
                "parent_asin": str(record.get("parent_asin", "")),
                "rating": int(record.get("rating", 0) or 0), # ensure rating is an integer
                "title": str(record.get("title", "")),
                "text": str(record.get("text", "")),
                "images": json.dumps(images),

                # record.get("helpful_vote", 0) → fetches the helpful_vote value; returns 0 if missing.
                # The or 0 ensures that if the fetched value is something falsey (like None, "", or False), it still becomes 0.
                # int(...) converts it into an integer to ensure it’s a valid numeric type before insertion into the database.
                "helpful_vote": int(record.get("helpful_vote", 0) or 0), # ensure helpful_vote is an integer
                "verified_purchase": 1 if record.get("verified_purchase", False) else 0,
                "timestamp": int(record.get("timestamp", 0) or 0),
            }
# Appends the prepared row to the list of rows for batch insertion.
            rows.append(row)
            logging.info(f"Prepared row for insert: {row}")
        df = pl.DataFrame(rows)

# Inserts the DataFrame into ClickHouse in chunks.
# Converts the batch list into a Polars DataFrame for efficient bulk insertion.
# Writes data to ClickHouse table with specified concurrency.
        clickhouse.sql_write(
            df,
            schema=SCHEMA,
            table_name=TABLE,
            max_chunk=MAX_CHUNK,
            max_workers=MAX_WORKERS, # number of parallel threads for insertion
        )
# Logs the number of rows inserted.
        logging.info(f"Inserted batch of {len(rows)} rows")

    except Exception as e:
        logging.error(f"Error in batch insert: {e}")

# Main function to read the JSONL file and process it in batches using multithreading.
def ingest_file(file_path):
    logging.info(f"Starting ingestion from {file_path}")

    with open(file_path, "r") as f:
        # Reads the file line by line, accumulating records into batches.
        batch = []
        # Uses ThreadPoolExecutor to handle multiple batches in parallel.
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for line in f:
                record = json.loads(line)
                batch.append(record)

# When the batch size is reached, submits the batch for insertion and resets the batch list.
                if len(batch) >= BATCH_SIZE:
                    executor.submit(insert_batch, batch)
                    batch = []
# After finishing reading the file, ensures any remaining records in the last batch are processed.
            if batch:
                executor.submit(insert_batch, batch)

    logging.info("Finished ingestion")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Amazon reviews JSONL into ClickHouse")
    parser.add_argument(
        "file",
        metavar="FILE",
        type=str,
        help="Path to the JSONL file to ingest"
    )
    args = parser.parse_args()

    ingest_file(args.file)
