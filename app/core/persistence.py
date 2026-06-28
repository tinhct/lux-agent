# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from abc import ABC, abstractmethod
import json
import logging
import os
import random
import time
from typing import Any, List, Optional
from google.cloud import storage

logger = logging.getLogger(__name__)


class AuditRepository(ABC):
    """Abstract base repository interface for logging and storing audit reports."""

    @abstractmethod
    def append_record(self, record: dict[str, Any]) -> str:
        """Appends a new audit record to the repository. Returns a status string."""
        pass

    @abstractmethod
    def get_next_id(self) -> int:
        """Returns the next ID for a new record."""
        pass


class LocalFileAuditRepository(AuditRepository):
    """Concrete repository implementing local JSON file-based persistence."""

    def __init__(self, db_path: str = "audit_db.json"):
        self.db_path = db_path

    def _read_db(self) -> List[dict[str, Any]]:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    db = json.load(f)
                    if isinstance(db, list):
                        return db
            except Exception:
                pass
        return []

    def get_next_id(self) -> int:
        db = self._read_db()
        return len(db) + 1

    def append_record(self, record: dict[str, Any]) -> str:
        db = self._read_db()
        db.append(record)
        try:
            with open(self.db_path, "w") as f:
                json.dump(db, f, indent=2)
            return "Saved to Database successfully."
        except Exception as e:
            return f"Failed to save to database: {e}"


class GcsAuditRepository(AuditRepository):
    """Concrete repository implementing Google Cloud Storage audit logs."""

    def __init__(self, bucket_name: str, prefix: str = "audit_logs"):
        self.bucket_name = bucket_name
        self.prefix = prefix
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = storage.Client()
        return self._client

    def get_next_id(self) -> int:
        # Generate a unique, monotonic, positive 31-bit integer
        ms = int(time.time() * 1000) & 0x7fffffff
        return (ms + random.randint(0, 1000)) & 0x7fffffff

    def append_record(self, record: dict[str, Any]) -> str:
        try:
            bucket = self.client.bucket(self.bucket_name)
            filename = f"{self.prefix}/audit_{record['id']}_{record['timestamp']}.json"
            blob = bucket.blob(filename)
            blob.upload_from_string(
                json.dumps(record, indent=2), content_type="application/json"
            )
            logger.info("Audit record saved to GCS: gs://%s/%s", self.bucket_name, filename)
            return f"Saved to GCS bucket '{self.bucket_name}' successfully."
        except Exception as e:
            logger.error("Failed to save audit record to GCS: %s", e)
            return f"Failed to save to GCS: {e}"


def get_audit_repository(settings: Optional[Any] = None) -> AuditRepository:
    """Factory function returning the repository implementation based on environment settings."""
    if settings is None:
        from app.core.config import get_settings
        settings = get_settings()

    if settings.logs_bucket_name:
        return GcsAuditRepository(bucket_name=settings.logs_bucket_name)

    return LocalFileAuditRepository()
