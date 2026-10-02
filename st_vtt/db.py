"""SQLite persistence. Entities are stored as JSON documents with a revision counter."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Literal

SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    owner TEXT,
    playbook TEXT,
    name TEXT,
    data TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shared_sheets (
    id TEXT PRIMARY KEY,
    template TEXT NOT NULL,
    name TEXT,
    data TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT,
    data TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    author TEXT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    visibility TEXT
);
CREATE INDEX IF NOT EXISTS messages_ts ON messages(ts);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS applied_refs (
    user TEXT NOT NULL,
    client TEXT NOT NULL,
    ref INTEGER NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (user, client)
);
"""

# A browser's client id lasts one page load; forget ids unseen for this long.
APPLIED_REFS_TTL = 30 * 24 * 3600

Applied = tuple[str, str, int]
# The tables that hold documents. The helpers below put the name into their SQL, so only
# these can reach it (values are always bound parameters).
DocTable = Literal["characters", "shared_sheets", "records"]


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.execute("DELETE FROM applied_refs WHERE updated_at < ?", (time.time() - APPLIED_REFS_TTL,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --------------------------------------------------------------- documents
    # Characters, shared sheets and records are each a JSON document with the same bookkeeping
    # (revision, created_at, updated_at) and one column of their own: owner, template or kind.
    # `name`, and a character's `playbook`, are copies of the document's own fields; rows leave
    # them out, as `data` already holds them.

    _MIRRORED: dict[DocTable, tuple[str, ...]] = {
        "characters": ("name", "playbook"),
        "shared_sheets": ("name",),
        "records": ("name",),
    }

    @staticmethod
    def _doc_row(r: sqlite3.Row) -> dict[str, Any]:
        row = {k: r[k] for k in r.keys() if k not in ("data", "name", "playbook")}
        row["data"] = json.loads(r["data"])
        return row

    def _list(self, table: DocTable) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(f"SELECT * FROM {table} ORDER BY created_at").fetchall()
        return [self._doc_row(r) for r in rows]

    def _get(self, table: DocTable, eid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(f"SELECT * FROM {table} WHERE id=?", (eid,)).fetchone()
        return self._doc_row(row) if row else None

    def _insert(self, table: DocTable, eid: str, own: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        mirrored = self._MIRRORED[table]
        values = {
            "id": eid,
            **own,
            **{k: doc.get(k) for k in mirrored},
            "data": json.dumps(doc),
            "revision": 0,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._conn.execute(
                f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
                tuple(values.values()),
            )
            self._conn.commit()
        row = self._get(table, eid)
        assert row is not None
        return row

    def _save(self, table: DocTable, eid: str, doc: dict[str, Any], applied: Applied | None) -> int:
        """Persist a modified document; returns the new revision. KeyError if it is gone."""
        mirrored = self._MIRRORED[table]
        sets = "".join(f"{k}=?, " for k in mirrored)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE {table} SET {sets}data=?, revision=revision+1, updated_at=? WHERE id=?",
                (*(doc.get(k) for k in mirrored), json.dumps(doc), time.time(), eid),
            )
            if cur.rowcount == 0:
                raise KeyError(eid)
            rev = self._conn.execute(f"SELECT revision FROM {table} WHERE id=?", (eid,)).fetchone()[0]
            self._record_applied(applied)
            self._conn.commit()
        return int(rev)

    def _delete(self, table: DocTable, eid: str) -> bool:
        with self._lock:
            cur = self._conn.execute(f"DELETE FROM {table} WHERE id=?", (eid,))
            self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------- characters
    def list_characters(self) -> list[dict[str, Any]]:
        return self._list("characters")

    def get_character(self, cid: str) -> dict[str, Any] | None:
        return self._get("characters", cid)

    def insert_character(self, cid: str, owner: str | None, doc: dict[str, Any]) -> dict[str, Any]:
        return self._insert("characters", cid, {"owner": owner}, doc)

    def save_character(self, cid: str, doc: dict[str, Any], applied: Applied | None = None) -> int:
        return self._save("characters", cid, doc, applied)

    def set_character_owner(self, cid: str, owner: str | None) -> None:
        with self._lock:
            self._conn.execute("UPDATE characters SET owner=?, updated_at=? WHERE id=?", (owner, time.time(), cid))
            self._conn.commit()

    def delete_character(self, cid: str) -> bool:
        return self._delete("characters", cid)

    # ------------------------------------------------------------ shared sheets
    def list_shared(self) -> list[dict[str, Any]]:
        return self._list("shared_sheets")

    def get_shared(self, sid: str) -> dict[str, Any] | None:
        return self._get("shared_sheets", sid)

    def insert_shared(self, sid: str, template: str, doc: dict[str, Any]) -> dict[str, Any]:
        return self._insert("shared_sheets", sid, {"template": template}, doc)

    def save_shared(self, sid: str, doc: dict[str, Any], applied: Applied | None = None) -> int:
        return self._save("shared_sheets", sid, doc, applied)

    def delete_shared(self, sid: str) -> bool:
        return self._delete("shared_sheets", sid)

    # ---------------------------------------------------------------- records
    def list_records(self) -> list[dict[str, Any]]:
        return self._list("records")

    def get_record(self, rid: str) -> dict[str, Any] | None:
        return self._get("records", rid)

    def insert_record(self, rid: str, kind: str, doc: dict[str, Any]) -> dict[str, Any]:
        return self._insert("records", rid, {"kind": kind}, doc)

    def save_record(self, rid: str, doc: dict[str, Any], applied: Applied | None = None) -> int:
        return self._save("records", rid, doc, applied)

    def delete_record(self, rid: str) -> bool:
        return self._delete("records", rid)

    # ---------------------------------------------------------------- messages
    def add_message(
        self, author: str | None, kind: str, payload: dict[str, Any], visibility: list[str] | None = None
    ) -> dict[str, Any]:
        ts = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (ts, author, kind, payload, visibility) VALUES (?,?,?,?,?)",
                (ts, author, kind, json.dumps(payload), json.dumps(visibility) if visibility is not None else None),
            )
            self._conn.commit()
            mid = cur.lastrowid
        return {"id": mid, "ts": ts, "author": author, "kind": kind, "payload": payload, "visibility": visibility}

    def list_messages(self, limit: int | None = 200, before: int | None = None) -> list[dict[str, Any]]:
        """The latest `limit` messages (every one, for None) older than message `before`, oldest first."""
        # SQLite reads a negative LIMIT as no limit.
        bound = -1 if limit is None else limit
        with self._lock:
            if before is None:
                rows = self._conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (bound,)).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE id<? ORDER BY id DESC LIMIT ?", (before, bound)
                ).fetchall()
        return [self._message_row(r) for r in reversed(rows)]

    def get_message(self, mid: int) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return self._message_row(r) if r else None

    @staticmethod
    def _message_row(r: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": r["id"],
            "ts": r["ts"],
            "author": r["author"],
            "kind": r["kind"],
            "payload": json.loads(r["payload"]),
            "visibility": json.loads(r["visibility"]) if r["visibility"] else None,
        }

    def update_message(self, mid: int, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute("UPDATE messages SET payload=? WHERE id=?", (json.dumps(payload), mid))
            self._conn.commit()

    def clear_messages(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.commit()

    # -------------------------------------------------------------------- meta
    def get_meta(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))
            self._conn.commit()

    # ------------------------------------------------------------ applied refs
    # The highest patch ref applied from each (user, client), written in the same commit as the
    # patch itself, so a patch resent after a dropped connection (or a server restart) is known.

    def applied_ref(self, user: str, client: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT ref FROM applied_refs WHERE user=? AND client=?", (user, client)
            ).fetchone()
        return int(row[0]) if row else 0

    def _record_applied(self, applied: Applied | None) -> None:
        """Call with the lock held, before committing."""
        if applied is None:
            return
        self._conn.execute(
            "INSERT INTO applied_refs (user, client, ref, updated_at) VALUES (?,?,?,?)"
            " ON CONFLICT (user, client) DO UPDATE SET ref=max(ref, excluded.ref), updated_at=excluded.updated_at",
            (*applied, time.time()),
        )

    # ------------------------------------------------------------------ export
    def export_all(self) -> dict[str, Any]:
        return {
            "characters": self.list_characters(),
            "shared": self.list_shared(),
            "records": self.list_records(),
            "messages": self.list_messages(limit=None),
        }
