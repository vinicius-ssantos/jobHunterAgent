from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApplicationEventRecord:
    id: int
    application_id: int
    event_type: str
    occurred_at_utc: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ApplicationArtifactRecord:
    id: int
    application_id: int
    artifact_type: str
    path: str
    created_at_utc: str
    metadata: dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, sort_keys=True)


def _json_loads(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {"raw": value}
    return payload if isinstance(payload, dict) else {"raw": payload}


def record_application_event(
    connection: sqlite3.Connection,
    application_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    occurred_at_utc: str | None = None,
) -> ApplicationEventRecord:
    if application_id <= 0:
        raise ValueError("application_id must be positive")
    if not event_type.strip():
        raise ValueError("event_type must not be empty")

    occurred_at = occurred_at_utc or utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO application_events (application_id, event_type, occurred_at_utc, payload)
        VALUES (?, ?, ?, ?)
        """,
        (application_id, event_type.strip(), occurred_at, _json_dumps(payload)),
    )
    return ApplicationEventRecord(
        id=cursor.lastrowid,
        application_id=application_id,
        event_type=event_type.strip(),
        occurred_at_utc=occurred_at,
        payload=payload or {},
    )


def list_application_events(connection: sqlite3.Connection, application_id: int) -> list[ApplicationEventRecord]:
    rows = connection.execute(
        """
        SELECT id, application_id, event_type, occurred_at_utc, payload
        FROM application_events
        WHERE application_id = ?
        ORDER BY occurred_at_utc ASC, id ASC
        """,
        (application_id,),
    ).fetchall()
    return [
        ApplicationEventRecord(
            id=row[0],
            application_id=row[1],
            event_type=row[2],
            occurred_at_utc=row[3],
            payload=_json_loads(row[4]),
        )
        for row in rows
    ]


def record_application_artifact(
    connection: sqlite3.Connection,
    application_id: int,
    artifact_type: str,
    path: str | Path,
    metadata: dict[str, Any] | None = None,
    *,
    created_at_utc: str | None = None,
) -> ApplicationArtifactRecord:
    if application_id <= 0:
        raise ValueError("application_id must be positive")
    if not artifact_type.strip():
        raise ValueError("artifact_type must not be empty")

    path_text = str(path).strip()
    if not path_text:
        raise ValueError("path must not be empty")

    created_at = created_at_utc or utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO application_artifacts (application_id, artifact_type, path, created_at_utc, metadata)
        VALUES (?, ?, ?, ?, ?)
        """,
        (application_id, artifact_type.strip(), path_text, created_at, _json_dumps(metadata)),
    )
    return ApplicationArtifactRecord(
        id=cursor.lastrowid,
        application_id=application_id,
        artifact_type=artifact_type.strip(),
        path=path_text,
        created_at_utc=created_at,
        metadata=metadata or {},
    )


def list_application_artifacts(connection: sqlite3.Connection, application_id: int) -> list[ApplicationArtifactRecord]:
    rows = connection.execute(
        """
        SELECT id, application_id, artifact_type, path, created_at_utc, metadata
        FROM application_artifacts
        WHERE application_id = ?
        ORDER BY created_at_utc ASC, id ASC
        """,
        (application_id,),
    ).fetchall()
    return [
        ApplicationArtifactRecord(
            id=row[0],
            application_id=row[1],
            artifact_type=row[2],
            path=row[3],
            created_at_utc=row[4],
            metadata=_json_loads(row[5]),
        )
        for row in rows
    ]
