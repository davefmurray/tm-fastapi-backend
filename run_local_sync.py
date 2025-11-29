#!/usr/bin/env python3
"""
Local Sync Script
Runs sync operations locally, bypassing Railway HTTP timeouts.
"""

import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.sync.snapshot_builder import SnapshotBuilder, get_snapshot_builder
from app.sync.metrics_aggregator import MetricsAggregator, get_metrics_aggregator


def main():
    print("=" * 60)
    print("LOCAL SYNC SCRIPT")
    print("=" * 60)

    shop_id = int(os.getenv("TM_SHOP_ID", "6212"))

    # Date range: last 30 days
    today = date.today()
    start_date = (today - timedelta(days=30)).isoformat()
    end_date = today.isoformat()

    print(f"\nShop ID: {shop_id}")
    print(f"Date range: {start_date} to {end_date}")

    # Step 1: Build snapshots
    print("\n" + "-" * 40)
    print("STEP 1: Building RO Snapshots...")
    print("-" * 40)

    builder = get_snapshot_builder()
    snapshot_result = builder.build_snapshots_for_period(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date
    )

    print(f"Snapshot Result: {snapshot_result}")

    if snapshot_result.get("status") == "error":
        print(f"ERROR: {snapshot_result.get('message')}")
        return

    # Step 2: Rebuild daily metrics
    print("\n" + "-" * 40)
    print("STEP 2: Rebuilding Daily Metrics...")
    print("-" * 40)

    aggregator = get_metrics_aggregator()
    metrics_result = aggregator.rebuild_daily_metrics(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date
    )

    print(f"Metrics Result: {metrics_result}")

    print("\n" + "=" * 60)
    print("SYNC COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
