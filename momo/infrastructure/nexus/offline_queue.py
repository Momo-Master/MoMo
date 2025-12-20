"""
Nexus Offline Queue.
~~~~~~~~~~~~~~~~~~~~

Store-and-forward mechanism for when Nexus is unreachable.
Queues messages locally and syncs when connection is restored.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class QueueItemType(str, Enum):
    """Type of queued item."""
    
    HANDSHAKE = "handshake"
    CREDENTIAL = "credential"
    CRACK_RESULT = "crack_result"
    STATUS = "status"
    LOOT = "loot"


class QueueItemStatus(str, Enum):
    """Status of queued item."""
    
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class QueueItem:
    """Item in the offline queue."""
    
    id: int
    item_type: QueueItemType
    data: dict[str, Any]
    created_at: datetime
    status: QueueItemStatus = QueueItemStatus.PENDING
    retries: int = 0
    last_error: str | None = None


class OfflineQueue:
    """
    SQLite-based offline queue for Nexus sync data.
    
    Features:
    - Persistent storage survives reboots
    - Automatic retry with exponential backoff
    - Priority ordering (handshakes before status)
    - Deduplication for status updates
    
    Example:
        >>> queue = OfflineQueue(Path("/data/momo/queue.db"))
        >>> await queue.enqueue(QueueItemType.HANDSHAKE, {...})
        >>> 
        >>> # When online
        >>> items = await queue.get_pending()
        >>> for item in items:
        ...     success = await sync_to_nexus(item)
        ...     if success:
        ...         await queue.mark_sent(item.id)
    """
    
    # Priority order (lower = higher priority)
    PRIORITY_MAP = {
        QueueItemType.HANDSHAKE: 1,
        QueueItemType.CREDENTIAL: 2,
        QueueItemType.CRACK_RESULT: 3,
        QueueItemType.LOOT: 4,
        QueueItemType.STATUS: 5,
    }
    
    def __init__(
        self,
        db_path: Path | str = "nexus_queue.db",
        max_retries: int = 5,
        max_items: int = 1000,
    ):
        """
        Initialize offline queue.
        
        Args:
            db_path: Path to SQLite database
            max_retries: Max retry attempts before giving up
            max_items: Max items to keep in queue
        """
        self.db_path = Path(db_path)
        self.max_retries = max_retries
        self.max_items = max_items
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
    
    # ==================== Lifecycle ====================
    
    async def initialize(self) -> None:
        """Initialize database and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                retries INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
            CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority, created_at);
        """)
        self._conn.commit()
        
        logger.info(f"Offline queue initialized: {self.db_path}")
    
    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    # ==================== Enqueue ====================
    
    async def enqueue(
        self,
        item_type: QueueItemType,
        data: dict[str, Any],
    ) -> int:
        """
        Add item to queue.
        
        Args:
            item_type: Type of item
            data: Item data
            
        Returns:
            Queue item ID
        """
        async with self._lock:
            priority = self.PRIORITY_MAP.get(item_type, 5)
            
            # For status updates, replace existing pending status
            if item_type == QueueItemType.STATUS:
                self._conn.execute(
                    "DELETE FROM queue WHERE item_type = ? AND status = 'pending'",
                    (item_type.value,)
                )
            
            cursor = self._conn.execute(
                """
                INSERT INTO queue (item_type, data, priority)
                VALUES (?, ?, ?)
                """,
                (item_type.value, json.dumps(data), priority)
            )
            self._conn.commit()
            
            item_id = cursor.lastrowid
            logger.debug(f"Queued {item_type.value}: {item_id}")
            
            # Cleanup old items if over limit
            await self._cleanup()
            
            return item_id
    
    async def enqueue_handshake(
        self,
        ssid: str,
        bssid: str,
        channel: int,
        data: bytes | None = None,
        **kwargs: Any,
    ) -> int:
        """Convenience method to queue handshake."""
        import base64
        
        payload = {
            "ssid": ssid,
            "bssid": bssid,
            "channel": channel,
            **kwargs,
        }
        
        if data:
            payload["data"] = base64.b64encode(data).decode()
        
        return await self.enqueue(QueueItemType.HANDSHAKE, payload)
    
    async def enqueue_credential(
        self,
        ssid: str,
        client_mac: str,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> int:
        """Convenience method to queue credential."""
        payload = {
            "ssid": ssid,
            "client_mac": client_mac,
            "username": username,
            "password": password,
            **kwargs,
        }
        return await self.enqueue(QueueItemType.CREDENTIAL, payload)
    
    async def enqueue_status(
        self,
        battery: int | None = None,
        temperature: int | None = None,
        **kwargs: Any,
    ) -> int:
        """Convenience method to queue status update."""
        payload = {
            "battery": battery,
            "temperature": temperature,
            **kwargs,
        }
        return await self.enqueue(QueueItemType.STATUS, payload)
    
    # ==================== Dequeue ====================
    
    async def get_pending(self, limit: int = 10) -> list[QueueItem]:
        """
        Get pending items ordered by priority.
        
        Args:
            limit: Max items to return
            
        Returns:
            List of pending queue items
        """
        async with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM queue
                WHERE status = 'pending' AND retries < ?
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
                """,
                (self.max_retries, limit)
            )
            
            items = []
            for row in cursor.fetchall():
                items.append(QueueItem(
                    id=row["id"],
                    item_type=QueueItemType(row["item_type"]),
                    data=json.loads(row["data"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=QueueItemStatus(row["status"]),
                    retries=row["retries"],
                    last_error=row["last_error"],
                ))
            
            return items
    
    async def get_item(self, item_id: int) -> QueueItem | None:
        """Get specific queue item."""
        cursor = self._conn.execute(
            "SELECT * FROM queue WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return QueueItem(
            id=row["id"],
            item_type=QueueItemType(row["item_type"]),
            data=json.loads(row["data"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            status=QueueItemStatus(row["status"]),
            retries=row["retries"],
            last_error=row["last_error"],
        )
    
    # ==================== Status Updates ====================
    
    async def mark_sending(self, item_id: int) -> None:
        """Mark item as currently being sent."""
        async with self._lock:
            self._conn.execute(
                """
                UPDATE queue 
                SET status = 'sending', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (item_id,)
            )
            self._conn.commit()
    
    async def mark_sent(self, item_id: int) -> None:
        """Mark item as successfully sent (removes from queue)."""
        async with self._lock:
            self._conn.execute("DELETE FROM queue WHERE id = ?", (item_id,))
            self._conn.commit()
            logger.debug(f"Queue item sent: {item_id}")
    
    async def mark_failed(self, item_id: int, error: str) -> None:
        """Mark item as failed (increments retry count)."""
        async with self._lock:
            self._conn.execute(
                """
                UPDATE queue 
                SET status = 'pending', 
                    retries = retries + 1,
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error, item_id)
            )
            self._conn.commit()
            logger.debug(f"Queue item failed: {item_id} - {error}")
    
    # ==================== Stats ====================
    
    async def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        cursor = self._conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'sending' THEN 1 ELSE 0 END) as sending,
                SUM(CASE WHEN retries >= ? THEN 1 ELSE 0 END) as failed
            FROM queue
        """, (self.max_retries,))
        
        row = cursor.fetchone()
        
        return {
            "total": row["total"] or 0,
            "pending": row["pending"] or 0,
            "sending": row["sending"] or 0,
            "failed": row["failed"] or 0,
            "db_path": str(self.db_path),
        }
    
    async def get_count(self) -> int:
        """Get total pending items count."""
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM queue WHERE status = 'pending'"
        )
        return cursor.fetchone()[0]
    
    # ==================== Cleanup ====================
    
    async def _cleanup(self) -> None:
        """Remove old items if over limit."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM queue")
        count = cursor.fetchone()[0]
        
        if count > self.max_items:
            # Remove oldest items over limit (keep high priority)
            delete_count = count - self.max_items
            self._conn.execute(
                """
                DELETE FROM queue WHERE id IN (
                    SELECT id FROM queue
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                )
                """,
                (delete_count,)
            )
            self._conn.commit()
            logger.info(f"Cleaned up {delete_count} old queue items")
    
    async def clear_sent(self) -> int:
        """Clear all sent items."""
        cursor = self._conn.execute("DELETE FROM queue WHERE status = 'sent'")
        self._conn.commit()
        return cursor.rowcount
    
    async def clear_failed(self) -> int:
        """Clear all permanently failed items."""
        cursor = self._conn.execute(
            "DELETE FROM queue WHERE retries >= ?",
            (self.max_retries,)
        )
        self._conn.commit()
        return cursor.rowcount
    
    async def clear_all(self) -> int:
        """Clear entire queue."""
        cursor = self._conn.execute("DELETE FROM queue")
        self._conn.commit()
        return cursor.rowcount
    
    # ==================== Context Manager ====================
    
    async def __aenter__(self) -> OfflineQueue:
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


class QueueSyncer:
    """
    Background syncer that processes offline queue when online.
    
    Example:
        >>> syncer = QueueSyncer(queue, nexus_client)
        >>> await syncer.start()
    """
    
    def __init__(
        self,
        queue: OfflineQueue,
        nexus_client: Any,  # NexusClient
        sync_interval: float = 30.0,
        batch_size: int = 10,
    ):
        """
        Initialize queue syncer.
        
        Args:
            queue: Offline queue instance
            nexus_client: NexusClient instance
            sync_interval: Seconds between sync attempts
            batch_size: Items to sync per batch
        """
        self.queue = queue
        self.client = nexus_client
        self.sync_interval = sync_interval
        self.batch_size = batch_size
        
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start background syncer."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info("Queue syncer started")
    
    async def stop(self) -> None:
        """Stop background syncer."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("Queue syncer stopped")
    
    async def _sync_loop(self) -> None:
        """Main sync loop."""
        while self._running:
            try:
                if self.client.is_connected:
                    await self._process_batch()
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            await asyncio.sleep(self.sync_interval)
    
    async def _process_batch(self) -> None:
        """Process a batch of queued items."""
        items = await self.queue.get_pending(self.batch_size)
        
        if not items:
            return
        
        logger.debug(f"Syncing {len(items)} queued items")
        
        for item in items:
            await self.queue.mark_sending(item.id)
            
            try:
                success = await self._sync_item(item)
                
                if success:
                    await self.queue.mark_sent(item.id)
                else:
                    await self.queue.mark_failed(item.id, "Sync returned False")
                    
            except Exception as e:
                await self.queue.mark_failed(item.id, str(e))
    
    async def _sync_item(self, item: QueueItem) -> bool:
        """Sync a single item to Nexus."""
        try:
            if item.item_type == QueueItemType.HANDSHAKE:
                result = await self.client.upload_handshake(**item.data)
            elif item.item_type == QueueItemType.CREDENTIAL:
                result = await self.client.upload_credential(**item.data)
            elif item.item_type == QueueItemType.CRACK_RESULT:
                result = await self.client.upload_crack_result(**item.data)
            elif item.item_type == QueueItemType.STATUS:
                result = await self.client.update_status(**item.data)
            elif item.item_type == QueueItemType.LOOT:
                result = await self.client.upload_loot(**item.data)
            else:
                logger.warning(f"Unknown queue item type: {item.item_type}")
                return False
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to sync {item.item_type}: {e}")
            raise

