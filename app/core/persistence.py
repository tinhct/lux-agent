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
import os
from typing import Any, List


class AuditRepository(ABC):
    """Abstract base repository interface for logging and storing audit reports."""

    @abstractmethod
    def append_record(self, record: dict[str, Any]) -> str:
        """Appends a new audit record to the repository. Returns a status string."""
        pass

    @abstractmethod
    def get_next_id(self) -> int:
        """Returns the next auto-incrementing ID for a new record."""
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


def get_audit_repository() -> AuditRepository:
    """Factory function returning the configured repository implementation."""
    return LocalFileAuditRepository()
