"""
HAMMY — Distributed Lease Management for Simulation Workers (`services/world_worker/lease.py`).
Provides per-pet mutual exclusion locks via the `worker_leases` table with:
  - Atomic compare-and-swap (CAS) version bumping.
  - Automatic expiration and takeover of abandoned leases.
  - Safe release and renewal mechanisms.
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from infrastructure.database.models import WorkerLease


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    """Ensures datetime is timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class LeaseManager:
    """Manages distributed leases for worker instances to guarantee single-writer per pet."""

    def __init__(self, default_ttl_sec: float = 30.0):
        self.default_ttl_sec = default_ttl_sec

    def acquire_lease(
        self,
        session: Session,
        pet_id: str,
        worker_id: str,
        ttl_sec: Optional[float] = None,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Acquires an exclusive lease on a pet for worker_id.
        Returns True if acquired or renewed; False if currently held by another live worker.
        """
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        expires_at = curr_time + datetime.timedelta(seconds=ttl)

        lease = session.get(WorkerLease, pet_id)
        if lease is None:
            new_lease = WorkerLease(
                pet_id=pet_id,
                worker_id=worker_id,
                acquired_at=curr_time,
                expires_at=expires_at,
                version=1,
            )
            session.add(new_lease)
            try:
                session.flush()
                return True
            except IntegrityError:
                session.rollback()
                # Concurrent insert race; retry via update logic below
                lease = session.get(WorkerLease, pet_id)
                if lease is None:
                    return False

        # Existing lease check
        lease_expires = _ensure_utc(lease.expires_at)
        is_expired = lease_expires <= curr_time
        is_owner = lease.worker_id == worker_id

        if is_expired or is_owner:
            # Atomic CAS update using current version
            rows = (
                session.query(WorkerLease)
                .filter(
                    WorkerLease.pet_id == pet_id,
                    WorkerLease.version == lease.version,
                )
                .update(
                    {
                        "worker_id": worker_id,
                        "acquired_at": curr_time,
                        "expires_at": expires_at,
                        "version": WorkerLease.version + 1,
                    }
                )
            )
            session.flush()
            return rows > 0

        # Lease is held by another active worker and unexpired
        return False

    def renew_lease(
        self,
        session: Session,
        pet_id: str,
        worker_id: str,
        ttl_sec: Optional[float] = None,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """Renews an active lease owned by worker_id."""
        return self.acquire_lease(session, pet_id, worker_id, ttl_sec=ttl_sec, now=now)

    def release_lease(
        self,
        session: Session,
        pet_id: str,
        worker_id: str,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Releases an active lease by expiring it immediately.
        Returns True if released; False if lease was not found or owned by someone else.
        """
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        expired_time = curr_time - datetime.timedelta(seconds=1)

        rows = (
            session.query(WorkerLease)
            .filter(
                WorkerLease.pet_id == pet_id,
                WorkerLease.worker_id == worker_id,
            )
            .update(
                {
                    "expires_at": expired_time,
                    "version": WorkerLease.version + 1,
                }
            )
        )
        session.flush()
        return rows > 0

    def is_lease_active(
        self,
        session: Session,
        pet_id: str,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """Checks if a valid, active lease currently exists for pet_id."""
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        lease = session.get(WorkerLease, pet_id)
        if not lease:
            return False
        return _ensure_utc(lease.expires_at) > curr_time

