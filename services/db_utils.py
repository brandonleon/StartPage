import sqlite3
from math import floor
from os import mkdir
from os.path import dirname, isdir, join, realpath
from time import time
from typing import Dict, Optional
from uuid import uuid4

import timeago
from packaging.version import parse

db_path = realpath(join(dirname(__file__), "..", "data", "links.db"))


# Get count of links in database
# Used for pagination
# TODO: return count of links and pages.
def get_count(batch: Optional[int] = 20) -> int:
    """
    Get count of links in database.

    Parameters:
        batch (Optional[int]): Number of links to return per page.

    Returns:
        int: Count of links in database.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) fROM links")
    count = cur.fetchone()[0]
    con.close()
    return floor(count / batch)


# Get individual link
def get_link(link_id: str) -> sqlite3.Row:
    """
    Get link by id.

    Parameters:
        link_id (str): Link id.

    Returns:
        Sqlite3.Row: Link.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT id, name, url fROM links WHERE id = :link_id", {"link_id": link_id}
    )
    link = cur.fetchone()
    # update accessed time and rank
    cur.execute(
        "UPDATE links SET accessed = :accessed, rank = rank + 1 WHERE id = :link_id",
        {"accessed": int(time()), "link_id": link_id}
    )
    con.commit()
    con.close()
    return link


# Get links in batches of 20
def get_links(page: int = 0, batch: int = 20):
    """
    Get links in batches of n, or 20 if n not supplied.

    Parameters:
        page (int): Page number.
        batch (int): Number of links to return per page.

    Returns:
        list: List of links.
    """
    page *= batch

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    cur = con.cursor()
    cur.execute(
        "SELECT id, url, name, rank, accessed fROM links ORDER BY rank DESC LIMIT :page, :batch;",
        {"page": page, "batch": batch},
    )
    rows = cur.fetchall()
    return [
        {
            "id": row["id"],
            "url": row["url"],
            "name": row["name"],
            "rank": row["rank"],
            "accessed": timeago.format(row["accessed"]),
        }
        for row in rows
    ]


# delete link by id
def delete_link(link_id: str) -> None:
    """
    Delete link from database.
    TODO: return success or failure.

    Parameters:
        link_id (str): Link id.
    Returns
        None: None.

    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("DELETE FROM links WHERE id = :link_id", {"link_id": link_id})
    con.commit()
    con.close()


# initialize database
def init_db(cur_version: str) -> None:
    """Check if database exists, if not create it.

    Parameters:
        None.

    Returns:
        None: None.
    """
    app_version = parse(cur_version)
    if not isdir(dirname(db_path)):
        mkdir(dirname(db_path))

    if not isdir(join(dirname(db_path), "../static")):
        mkdir(join(dirname(db_path), "../static"))

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='links';")
    result = cur.fetchone()
    if result is None:
        with open(
            join(realpath(join(dirname(__file__), "../sql_scripts", "db_v1.sql"))), "r"
        ) as sql_file:
            cur.executescript(sql_file.read())
            con.commit()


# add link to database
def save_link(name: str, url: str, link_id: Optional[str] = None) -> None:
    """
    Save link to database, or update existing link with a new name or url.

    If id is not provided, a new id will be generated, and inserted into the database.
    if id is provided, the link will be updated.

    Parameters:
        name (str): Link name.
        url (str): Link url.
        link_id (Optional[str]): Link id.

    Returns:
        None: None.
        TODO: Return ID of newly created link.
        TODO: new link rank should be an average of all existing links.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    if link_id is None:
        with con:
            cur.execute(
                "INSERT INTO links (id, url, name, rank, accessed) VALUES (:id, :url, :name, :rank, :accessed)",
                {
                    "id": str(uuid4()),
                    "url": url,
                    "name": name,
                    "rank": 1,
                    "accessed": int(time()),
                },
            )
    else:
        with con:
            cur.execute(
                "UPDATE links SET name = :name, url = :url WHERE id = :id",
                {
                    "id": link_id,
                    "name": name,
                    "url": url,
                },
            )


# Read config from data
def read_config() -> Dict[str, str]:
    """
    Read config from database.

    Returns:
        Dict[str, str]: Config.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT name, value fROM metadata;")
    d = {row["name"]: row["value"] for row in cur.fetchall()}
    con.close()
    return d


# Upgrade the database
def upgrade_db(cur_version: str, desired_version: str) -> None:
    """
    Upgrade the database.

    Parameters:
        cur_version (str): Current version of the database.
        desired_version (str): Desired version of the database.

    Returns:
        None: None.
    """
    migration_script = f"v{cur_version}_to_v{desired_version}.sql"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    with open(
        join(realpath(join(dirname(__file__), "../sql_scripts", migration_script))), "r"
    ) as sql_file:
        cur.executescript(sql_file.read())
        con.commit()
