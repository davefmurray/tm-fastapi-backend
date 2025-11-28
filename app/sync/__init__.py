"""
TM Data Warehouse Sync Module

Syncs Tekmetric API data to Supabase warehouse tables.
"""

from .warehouse_client import get_warehouse_client
from .sync_base import SyncBase
from .sync_employees import sync_employees
from .sync_customers import sync_customers
from .sync_vehicles import sync_vehicles
from .sync_repair_orders import sync_repair_orders
from .snapshot_builder import get_snapshot_builder, SnapshotBuilder
from .metrics_aggregator import get_metrics_aggregator, MetricsAggregator

__all__ = [
    "get_warehouse_client",
    "SyncBase",
    "sync_employees",
    "sync_customers",
    "sync_vehicles",
    "sync_repair_orders",
    "get_snapshot_builder",
    "SnapshotBuilder",
    "get_metrics_aggregator",
    "MetricsAggregator",
]
