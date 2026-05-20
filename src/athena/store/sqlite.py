from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from athena.schemas import TaskSnapshot


@dataclass
class SQLiteTaskStore:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute("create table if not exists tasks (id text primary key, payload text not null)")

    def save_snapshot(self, snapshot: TaskSnapshot) -> None:
        payload = snapshot.model_dump_json()
        with sqlite3.connect(self.path) as con:
            con.execute("insert or replace into tasks(id, payload) values (?, ?)", (snapshot.id, payload))

    def load_snapshot(self, task_id: str) -> TaskSnapshot | None:
        with sqlite3.connect(self.path) as con:
            row = con.execute("select payload from tasks where id=?", (task_id,)).fetchone()
        if not row:
            return None
        return TaskSnapshot.model_validate(json.loads(row[0]))
