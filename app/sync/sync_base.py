"""
Base class for sync operations

Provides common functionality for all sync modules:
- Sync log management
- Cursor tracking
- Error handling
- Raw payload storage
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass, field

from app.services.tm_client import TekmetricClient, get_tm_client
from app.sync.warehouse_client import WarehouseClient, get_warehouse_client


@dataclass
class SyncStats:
    """Track sync operation statistics"""
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[Dict] = field(default_factory=list)

    def add_error(self, entity_type: str, entity_id: Any, error: str):
        self.errors.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "error": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


class SyncBase:
    """Base class for sync operations"""

    def __init__(
        self,
        tm_client: Optional[TekmetricClient] = None,
        warehouse: Optional[WarehouseClient] = None
    ):
        self.tm = tm_client or get_tm_client()
        self.warehouse = warehouse or get_warehouse_client()
        self.stats = SyncStats()
        self.log_id: Optional[str] = None
        self.shop_uuid: Optional[str] = None
        self.tm_shop_id: Optional[int] = None
        self.store_raw_payloads: bool = False  # Enable for debugging

    async def init_shop(self, tm_shop_id: int) -> str:
        """Initialize shop context, returns shop UUID"""
        self.tm_shop_id = tm_shop_id
        self.shop_uuid = await self.warehouse.get_shop_uuid(tm_shop_id)
        if not self.shop_uuid:
            raise ValueError(f"Shop {tm_shop_id} not found in warehouse. Run shop sync first.")
        return self.shop_uuid

    async def start_sync(
        self,
        sync_type: str,
        entity_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Start a sync operation, returns log ID"""
        if not self.shop_uuid:
            raise ValueError("Shop not initialized. Call init_shop() first.")

        self.stats = SyncStats()  # Reset stats
        self.log_id = await self.warehouse.create_sync_log(
            shop_uuid=self.shop_uuid,
            sync_type=sync_type,
            entity_type=entity_type,
            metadata=metadata
        )
        return self.log_id

    async def complete_sync(self, status: str = "completed") -> None:
        """Complete sync operation with final stats"""
        if not self.log_id:
            return

        await self.warehouse.update_sync_log(
            log_id=self.log_id,
            status=status,
            records_fetched=self.stats.fetched,
            records_created=self.stats.created,
            records_updated=self.stats.updated,
            records_skipped=self.stats.skipped,
            error_count=len(self.stats.errors),
            errors=self.stats.errors if self.stats.errors else None
        )

    async def fail_sync(self, error: str) -> None:
        """Mark sync as failed"""
        self.stats.add_error("sync", None, error)
        await self.complete_sync(status="failed")

    async def store_payload(
        self,
        endpoint: str,
        response: Dict,
        tm_entity_id: Optional[int] = None,
        request_params: Optional[Dict] = None
    ) -> None:
        """Store raw API response for debugging"""
        if self.store_raw_payloads and self.shop_uuid:
            await self.warehouse.store_raw_payload(
                shop_uuid=self.shop_uuid,
                endpoint=endpoint,
                response_payload=response,
                tm_entity_id=tm_entity_id,
                request_params=request_params
            )

    async def get_cursor(self, entity_type: str) -> Optional[Dict]:
        """Get sync cursor for entity type"""
        if not self.shop_uuid:
            return None
        return await self.warehouse.get_sync_cursor(self.shop_uuid, entity_type)

    async def update_cursor(
        self,
        entity_type: str,
        last_tm_updated: Optional[datetime] = None,
        last_tm_id: Optional[int] = None,
        cursor_data: Optional[Dict] = None
    ) -> None:
        """Update sync cursor"""
        if self.shop_uuid:
            await self.warehouse.update_sync_cursor(
                shop_uuid=self.shop_uuid,
                entity_type=entity_type,
                last_tm_updated=last_tm_updated,
                last_tm_id=last_tm_id,
                cursor_data=cursor_data
            )
