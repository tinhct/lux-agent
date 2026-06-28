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

import json
import os
import pytest
from app.core.persistence import LocalFileAuditRepository


@pytest.fixture
def temp_db_file(tmp_path):
    """Fixture to provide a clean temporary file path for the audit database."""
    return str(tmp_path / "test_audit_db.json")


def test_persistence_empty_db_id(temp_db_file):
    """Verify that an empty/missing database starts with record ID 1."""
    repo = LocalFileAuditRepository(temp_db_file)
    assert repo.get_next_id() == 1


def test_persistence_append_record(temp_db_file):
    """Verify appending records writes to the local file and increments IDs correctly."""
    repo = LocalFileAuditRepository(temp_db_file)
    
    record_1 = {"id": 1, "test": "data_1"}
    status_1 = repo.append_record(record_1)
    assert "success" in status_1.lower()
    assert repo.get_next_id() == 2

    record_2 = {"id": 2, "test": "data_2"}
    status_2 = repo.append_record(record_2)
    assert "success" in status_2.lower()
    assert repo.get_next_id() == 3

    # Load file manually to check contents
    with open(temp_db_file, "r") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0] == record_1
    assert data[1] == record_2
