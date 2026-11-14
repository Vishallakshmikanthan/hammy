"""
HAMMY — P2.2: World Worker Package (`services/world_worker`).
Implements persistent simulation worker with distributed leases, bounded catch-up chunks,
deterministic event generation, time scaling, pause/resume, and atomic transactions.
"""

from services.world_worker.catchup import CatchUpSimulator, generate_deterministic_event_id
from services.world_worker.lease import LeaseManager
from services.world_worker.worker import WorldWorker

__all__ = [
    "CatchUpSimulator",
    "generate_deterministic_event_id",
    "LeaseManager",
    "WorldWorker",
]

