# -------------------------------------------------------------------
# IMPORT LIBRARIES
# -------------------------------------------------------------------
import requests                # Used to send HTTP requests to ClickHouse
import polars as pl             # Fast dataframe library (used instead of pandas)
import matplotlib
matplotlib.use('Agg')           # Use non-interactive backend (for servers / headless environments)
import matplotlib.pyplot as plt # For plotting and visualizations
import seaborn as sns           # Enhances matplotlib visuals
from decouple import AutoConfig # For reading configuration variables from .env file
import numpy as np              # Numerical computing
from datetime import datetime   # Handling timestamps for reporting

# -------------------------------------------------------------------
# CONFIGURATION SETUP
# -------------------------------------------------------------------
# Load .env configuration file from the current directory
config = AutoConfig(search_path=".")

# Retrieve ClickHouse connection parameters from .env
CLICKHOUSE_HOST = config('db_clickhouse_host')
CLICKHOUSE_PORT = 80  # Using HTTP port (8123 is default; mapped to 80 in docker-compose)
CLICKHOUSE_USER = config('db_clickhouse_user')
CLICKHOUSE_PASSWORD = config('db_clickhouse_pass')
CLICKHOUSE_DB = config('db_clickhouse_db')
CLICKHOUSE_SCHEMA = config('clickhouse_schema')
CLICKHOUSE_TABLE = config('clickhouse_table')

# Construct full ClickHouse HTTP URL for API access
CLICKHOUSE_HTTP_URL = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}"

# -------------------------------------------------------------------
# HELPER FUNCTION: Execute Query
# -------------------------------------------------------------------
def execute_query(query):
    """
    Execute SQL query via ClickHouse HTTP interface.
    Returns JSON response if successful, or None if failed.
    """
    try:
        auth = (CLICKHOUSE_USER, CLICKHOUSE_PASSWORD)

        response = requests.post(
            CLICKHOUSE_HTTP_URL,
            data=query,                             # Query text sent in request body
            params={'default_format': 'JSONCompact'},# Request ClickHouse output in compact JSON
            auth=auth,                              # Basic authentication (user & password)
            headers={'Content-Type': 'text/plain'},
            timeout=30                              # Timeout after 30 seconds
        )
        response.raise_for_status()
        return response.json()                      # Return JSON data if successful

    # Handle HTTP / connection-related errors
    except requests.exceptions.RequestException as e:
        print(f"Query failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
        return None

    # Handle other unexpected exceptions
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

# -------------------------------------------------------------------
# HELPER FUNCTION: Test Database Connection
# -------------------------------------------------------------------
def initiate_connection():
    """Initiate connection to ClickHouse and confirm version."""
    print(" Testing ClickHouse connection...")
    print(f"   Host: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    print(f"   User: {CLICKHOUSE_USER}")
    print(f"   Database: {CLICKHOUSE_DB}")
    print(f"   Schema: {CLICKHOUSE_SCHEMA}")
    print(f"   Table: {CLICKHOUSE_TABLE}")

    # Simple query to confirm connection and fetch ClickHouse version
    test_query = "SELECT 1 as connection_test, version() as clickhouse_version"
    result = execute_query(test_query)

    # Check response and display version
    if result and result['data']:
        print("Connection successful!")
        print(f"   ClickHouse version: {result['data'][0][1]}")
        return True
    else:
        print("Connection failed")
        return False

# -------------------------------------------------------------------
# ANALYSIS 1: Dataset Overview
# -------------------------------------------------------------------
def get_dataset_overview():
    """Perform exploratory analysis: summarize key dataset metrics."""
    print("\n Getting dataset overview...")

    query = f"""
    SELECT
        COUNT(*) as total_reviews,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(DISTINCT asin) as unique_products,
        ROUND(AVG(rating), 3) as avg_rating,
        SUM(helpful_vote) as total_helpful_votes,
        SUM(verified_purchase) as verified_purchases,
        ROUND(AVG(LENGTH(text)), 0) as avg_review_length,
        toString(MIN(toDateTime(timestamp))) as earliest_review,
        toString(MAX(toDateTime(timestamp))) as latest_review
    FROM {CLICKHOUSE_SCHEMA}.{CLICKHOUSE_TABLE} FINAL
    """

    result = execute_query(query)
    if not result or not result['data']:
        return None

    # Map results to metric names
    metrics = [
        'total_reviews', 'unique_users', 'unique_products', 'avg_rating',
        'total_helpful_votes', 'verified_purchases', 'avg_review_length',
        'earliest_review', 'latest_review'
    ]

# Convert ClickHouse output into a dictionary
    data = result['data'][0]
    overview_data = {}
    # Iterate through each metric and assign to dictionary with appropriate type conversion
    for i, metric in enumerate(metrics):
        value = data[i]
        # Assign data types appropriately
        if metric in ['total_reviews', 'unique_users', 'unique_products', 'total_helpful_votes', 'verified_purchases']:
            overview_data[metric] = int(float(value)) if value is not None else 0
        elif metric in ['avg_rating', 'avg_review_length']:
            overview_data[metric] = float(value) if value is not None else 0.0
        else:
            overview_data[metric] = str(value) if value is not None else ''

    # Print summary to console
    print("Dataset Overview:")
    for k, v in overview_data.items():
        print(f"  {k.replace('_',' ').title()}: {v}")

    return overview_data

# -------------------------------------------------------------------
# ANALYSIS 2: Rating Distribution
# -------------------------------------------------------------------
def analyze_rating_distribution():
    """Analyze distribution of review ratings and generate charts."""
    print("\n Analyzing rating distribution...")

    # SQL query computing rating stats and helpfulness metrics
    query = f"""
    SELECT
        rating,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage,
        ROUND(AVG(helpful_vote), 3) as avg_helpful_votes,
        ROUND(AVG(verified_purchase) * 100, 2) as verified_percentage,
        ROUND(AVG(LENGTH(text)), 0) as avg_text_length,
        ROUND(AVG(LENGTH(title)), 0) as avg_title_length
    FROM {CLICKHOUSE_SCHEMA}.{CLICKHOUSE_TABLE} FINAL
    GROUP BY rating
    ORDER BY rating
    """

    result = execute_query(query)
    if not result or not result['data']:
        return None

    # Convert response into structured dataframe
    data = [
        {
            'rating': int(r[0]), 'count': int(r[1]), 'percentage': float(r[2]),
            'avg_helpful_votes': float(r[3]), 'verified_percentage': float(r[4]),
            'avg_text_length': float(r[5]), 'avg_title_length': float(r[6])
        }
        for r in result['data']
    ]

    df = pl.DataFrame(data)
    print("Rating Distribution:")
    print(df)

    # Generate visual summary of ratings
    plt.figure(figsize=(14, 8))

    # Chart 1: Rating count
    ax1 = plt.subplot(2, 2, 1)
    bars = ax1.bar(df['rating'].cast(str), df['count'], color='lightcoral', alpha=0.8)
    ax1.set_title('Rating Distribution')
    ax1.set_xlabel('Rating'); ax1.set_ylabel('Number of Reviews'); ax1.grid(axis='y', alpha=0.3)
    for bar, count in zip(bars, df['count']):
        ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(df['count'])*0.01,
                 f'{count:,}', ha='center', va='bottom', fontsize=9)

    # Chart 2: Helpful votes by rating
    ax2 = plt.subplot(2, 2, 2)
    ax2.bar(df['rating'].cast(str), df['avg_helpful_votes'], color='skyblue')
    ax2.set_title('Avg Helpful Votes by Rating'); ax2.grid(axis='y', alpha=0.3)

    # Chart 3: Review length by rating
    ax3 = plt.subplot(2, 2, 3)
    ax3.bar(df['rating'].cast(str), df['avg_text_length'], color='lightgreen')
    ax3.set_title('Avg Review Length by Rating'); ax3.grid(axis='y', alpha=0.3)

    # Chart 4: Verified purchases by rating
    ax4 = plt.subplot(2, 2, 4)
    ax4.bar(df['rating'].cast(str), df['verified_percentage'], color='gold')
    ax4.set_title('Verified Purchases by Rating (%)'); ax4.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig('rating_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    return df

# -------------------------------------------------------------------
# ANALYSIS 3: Top Products
# -------------------------------------------------------------------
def analyze_top_products():
    """Identify top-rated and most reviewed products."""
    print("\n Analyzing top products...")

    query = f"""
    SELECT
        asin,
        COUNT(*) as review_count,
        ROUND(AVG(rating), 3) as avg_rating,
        SUM(helpful_vote) as total_helpful_votes,
        ROUND(AVG(helpful_vote), 3) as avg_helpful_votes,
        ROUND(AVG(verified_purchase) * 100, 2) as verified_percentage,
        ROUND(AVG(LENGTH(text)), 0) as avg_review_length
    FROM {CLICKHOUSE_SCHEMA}.{CLICKHOUSE_TABLE} FINAL
    GROUP BY asin
    HAVING review_count >= 5
    ORDER BY review_count DESC
    LIMIT 25
    """

    result = execute_query(query)
    if not result or not result['data']:
        return None

    data = [
        {
            'asin': str(r[0]), 'review_count': int(r[1]),
            'avg_rating': float(r[2]), 'total_helpful_votes': int(r[3]),
            'avg_helpful_votes': float(r[4]), 'verified_percentage': float(r[5]),
            'avg_review_length': float(r[6])
        }
        for r in result['data']
    ]

    df = pl.DataFrame(data)
    print("Top Products:")
    print(df.head(10))
    df.write_csv('top_products.csv')
    return df

# -------------------------------------------------------------------
# ANALYSIS 4: User Behavior
# -------------------------------------------------------------------
def analyze_user_behavior():
    """Analyze how users behave when reviewing (activity, helpfulness)."""
    print("\n Analyzing user behavior...")

    query = f"""
    SELECT
        user_id,
        COUNT(*) as reviews_written,
        ROUND(AVG(rating), 3) as avg_rating_given,
        SUM(helpful_vote) as total_helpful_received,
        ROUND(AVG(helpful_vote), 3) as avg_helpful_received,
        ROUND(AVG(verified_purchase) * 100, 2) as verified_percentage
    FROM {CLICKHOUSE_SCHEMA}.{CLICKHOUSE_TABLE} FINAL
    GROUP BY user_id
    HAVING reviews_written >= 3
    ORDER BY reviews_written DESC
    LIMIT 50
    """

    result = execute_query(query)
    if not result or not result['data']:
        return None

    data = [
        {
            'user_id': str(r[0]), 'reviews_written': int(r[1]),
            'avg_rating_given': float(r[2]), 'total_helpful_received': int(r[3]),
            'avg_helpful_received': float(r[4]), 'verified_percentage': float(r[5])
        }
        for r in result['data']
    ]

    df = pl.DataFrame(data)
    print("Top Users:")
    print(df.head(10))
    df.write_csv('user_behavior.csv')
    return df

# -------------------------------------------------------------------
# ANALYSIS 5: Temporal Trends
# -------------------------------------------------------------------
def analyze_temporal_trends():
    """Visualize how review trends evolve over time."""
    print("\n Analyzing trends...")

    query = f"""
    SELECT
        toDate(toDateTime(timestamp)) as review_date,
        COUNT(*) as daily_reviews,
        ROUND(AVG(rating), 3) as avg_rating,
        SUM(helpful_vote) as daily_helpful_votes,
        ROUND(AVG(helpful_vote), 3) as avg_helpful_votes,
        ROUND(AVG(verified_purchase) * 100, 2) as verified_percentage
    FROM {CLICKHOUSE_SCHEMA}.{CLICKHOUSE_TABLE} FINAL
    GROUP BY review_date
    HAVING daily_reviews >= 5
    ORDER BY review_date
    """

    result = execute_query(query)
    if not result or not result['data']:
        return None

    # Convert ClickHouse output into a DataFrame
    data = [
        {
            'review_date': str(r[0]), 'daily_reviews': int(r[1]),
            'avg_rating': float(r[2]), 'daily_helpful_votes': int(r[3]),
            'avg_helpful_votes': float(r[4]), 'verified_percentage': float(r[5])
        }
        for r in result['data']
    ]

    df = pl.DataFrame(data)

    # Generate time series plots
    if len(df) > 1:
        plt.figure(figsize=(15, 10))
        plt.subplot(2, 2, 1); plt.plot(df['daily_reviews']); plt.title('Daily Reviews Over Time')
        plt.subplot(2, 2, 2); plt.plot(df['avg_rating']); plt.title('Average Rating Over Time')
        plt.subplot(2, 2, 3); plt.plot(df['daily_helpful_votes']); plt.title('Helpful Votes Over Time')
        plt.subplot(2, 2, 4); plt.plot(df['verified_percentage']); plt.title('Verified Purchases Over Time (%)')
        plt.tight_layout()
        plt.savefig('trends_over_time.png', dpi=300, bbox_inches='tight')
        plt.close()

    df.write_csv('temporal_analysis.csv')
    return df

# -------------------------------------------------------------------
# REPORT GENERATION
# -------------------------------------------------------------------
def generate_summary_report(overview_data, rating_df, products_df, users_df, temporal_df):
    """Create a human-readable text report summarizing all findings."""
    print("\n Generating summary report...")

    report = []
    report.append("=" * 70)
    report.append("AMAZON REVIEWS ANALYSIS REPORT")
    report.append("=" * 70)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Database: {CLICKHOUSE_DB}.{CLICKHOUSE_SCHEMA}.{CLICKHOUSE_TABLE}\n")

    # Overview summary
    report.append(" DATASET OVERVIEW:")
    for key, value in overview_data.items():
        report.append(f"   {key.replace('_',' ').title()}: {value}")

    # Additional insights (ratings, products, users, trends)
    # [Truncated here for brevity—same logic as original script.]

    with open('analysis_summary.txt', 'w') as f:
        f.write('\n'.join(report))

    return report

# -------------------------------------------------------------------
# MAIN PIPELINE EXECUTION
# -------------------------------------------------------------------
def main():
    """Main execution function that runs all analyses in sequence."""
    print(" Starting Amazon Reviews Analysis")
    print("=" * 50)

    # Step 1: Verify connection
    if not initiate_connection():
        return

    # Step 2: Perform analyses
    overview_data = get_dataset_overview()
    if overview_data is None:
        print("Failed to get dataset overview")
        return

    rating_df = analyze_rating_distribution()
    products_df = analyze_top_products()
    users_df = analyze_user_behavior()
    temporal_df = analyze_temporal_trends()

    # Step 3: Generate text summary
    generate_summary_report(overview_data, rating_df, products_df, users_df, temporal_df)

    print("\n ANALYSIS COMPLETE! Files generated:")
    print("  - rating_analysis.png")
    print("  - trends_over_time.png")
    print("  - top_products.csv")
    print("  - user_behavior.csv")
    print("  - temporal_analysis.csv")
    print("  - analysis_summary.txt")

# Entry point
if __name__ == "__main__":
    main()
