import sqlite3
from os.path import dirname, join, realpath
from typing import Optional

from uuid import uuid4

db_path = realpath(join(dirname(__file__), "..", "data", "links.db"))


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

    def __init__(self, name: str, link_id: Optional[str] = None):
        """
        Creates a new tag, or loads an existing tag.

        Parameters:
        name (str): The tag name.
        """
        self.name = name
        self.link_id = link_id or None

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

        # If a link_id is supplied, add the tag and link to the tag_link_map table.
        if self.link_id:
            cur.execute(
                "SELECT tag_id, link_id FROM tag_link_map WHERE tag_id = :tag_id AND link_id = :link_id LIMIT 1",
                {"tag_id": self.id, "link_id": self.link_id},
            )
            if not cur.fetchone():
                with con as cur:
                    cur.execute(
                        "INSERT INTO tag_link_map (tag_id, link_id) VALUES (:tag_id, :link_id)",
                        {"tag_id": self.id, "link_id": self.link_id},
                    )
            self.update_count()

    # Update the tag count
    def update_count(self):
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

    # When deleting a tag, purge all references to it from the tag_link_map, and tags table.
    def delete(self) -> None:
        """
        Deletes the tag from the database.
        """
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "DELETE FROM tag_link_map WHERE tag_id = :id",
            {"id": self.id},
        )
        cur.execute(
            "DELETE FROM tags WHERE id = :id",
            {"id": self.id},
        )
        con.close()

    # When deleting a link, purge all references to it from the tag_link_map.
    def delete_link(self) -> None:
        """
        Deletes the link from the database.
        """
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "DELETE FROM tag_link_map WHERE link_id = :id",
            {"id": self.link_id},
        )
        con.close()

    @property
    def count(self) -> int:
        """
        Returns the number of times the tag is used.
        return: int: The tag count.
        """
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "SELECT count FROM tags WHERE id = :id LIMIT 1",
            {"id": self.id},
        )

        return cur.fetchone()["count"]
