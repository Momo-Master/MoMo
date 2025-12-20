"""
Nexus Integration for MoMo.
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Client library for syncing data with MoMo-Nexus central hub.
Handles handshake uploads, credential sync, status updates, and commands.

Features:
- HTTP API client for Nexus
- Command listener (WebSocket/polling)
- Offline queue (store-and-forward)
- Automatic sync manager

:copyright: (c) 2025 MoMo Team
:license: MIT
"""

from momo.infrastructure.nexus.client import NexusClient, NexusConfig
from momo.infrastructure.nexus.command_listener import (
    CommandStatus,
    NexusCommandListener,
    ReceivedCommand,
)
from momo.infrastructure.nexus.offline_queue import (
    OfflineQueue,
    QueueItem,
    QueueItemType,
    QueueSyncer,
)
from momo.infrastructure.nexus.sync import NexusSyncManager

__all__ = [
    # Client
    "NexusClient",
    "NexusConfig",
    # Command Listener
    "NexusCommandListener",
    "CommandStatus",
    "ReceivedCommand",
    # Offline Queue
    "OfflineQueue",
    "QueueItem",
    "QueueItemType",
    "QueueSyncer",
    # Sync Manager
    "NexusSyncManager",
]

