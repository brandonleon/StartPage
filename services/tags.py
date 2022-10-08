import sqlite3

from uuid import uuid4

from services.db_utils import db_path


class Tag:
    """
    Contains various methods for interacting with the tags table.

    Attributes:
    __init__: Creates a new tag, or loads an existing tag.
    update_count: Updates the count column on the tags table.

    Properties:
    id: The tag id.
    name: The tag name.
    count: The number of times the tag is used.
    """
    def __init__(self, name: str):
        """
        Creates a new tag, or loads an existing tag.

        Parameters:
        name (str): The tag name.
        """
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

    # Update the tag count
    def update_count(self) -> int:
        """
        Counts the number of times the tag is used, and updates the count column on the tags table.
        return: int: The new tag count.
        """
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "SELECT count(*) as count FROM tag_link_map WHERE tag_id = :id LIMIT 1",
            {"id": self.id},
        )

        count = cur.fetchone()["count"]
        # update the count in the tags table
        with con as cur:
            cur.execute(
                "UPDATE tags SET count = :count WHERE id = :id",
                {"id": self.id, "count": count},
            )

        return count
