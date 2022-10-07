import sqlite3

from uuid import uuid4

from services.db_utils import db_path


class Tag:
    def __init__(self, name: str):
        self.name = name

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "SELECT id, name FROM tags WHERE name = :name LIMIT 1",
            {"name": self.name},
        )

        if row := cur.fetchone():
            self.id = row["id"]
        else:
            self.id = str(uuid4())
            with con as cur:
                cur.execute(
                    "INSERT INTO tags (id, name, count) VALUES (:id, :name, 1)",
                    {"id": self.id, "name": self.name},
                )
