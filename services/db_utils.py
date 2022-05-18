import sqlite3
from math import floor
from os import mkdir
from os.path import dirname, isdir, join, realpath
from time import time
from typing import Dict, List, Optional
from uuid import uuid4

import timeago
import tomlkit

db_path = realpath(join(dirname(__file__), "..", "data", "links.db"))


# Get individual link
def get_link(link_id: str, increment_rank: bool) -> sqlite3.Row:
    """
    Get link by id.

    Parameters:
        link_id (str): Link id.
        increment_rank (bool): Increment link rank after selecting.
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
    if increment_rank:
        cur.execute(
            "UPDATE links SET accessed = :accessed, rank = rank + 1 WHERE id = :link_id",
            {"accessed": int(time()), "link_id": link_id},
        )
        con.commit()
    con.close()
    return link


# Get links in batches of 20
def get_links(page: int = 0, batch: int = 20) -> List[dict]:
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
        "SELECT id, url, name, rank, accessed fROM links "
        "ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC "
        "LIMIT :page, :batch;",
        {"page": page, "batch": batch},
    )
    rows = cur.fetchall()
    con.close()
    return [
        dict(
            id=row["id"],
            url=row["url"],
            name=row["name"],
            rank=row["rank"],
            accessed=timeago.format(row["accessed"]),
        )
        for row in rows
    ]


# delete link by id
def delete_link(link_id: str) -> bool:
    """
    Delete link from database.

    Parameters:
        link_id (str): Link id.
    Returns
        bool: True if link deleted, False if not.
    """
    con = sqlite3.connect(db_path)
    with con as cur:
        cur.execute("DELETE FROM links WHERE id = :link_id", {"link_id": link_id})
        return True


# initialize database
def init_db(cur_version: str) -> None:
    """Check if database exists, if not create it.

    Parameters:
        None.

    Returns:
        None: None.
    """
    schema = f"db_v{cur_version}.sql"

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
            join(realpath(join(dirname(__file__), "../sql_scripts", schema))), "r"
        ) as sql_file:
            cur.executescript(sql_file.read())
            con.commit()


# add link to database
def save_link(name: str, url: str, link_id: Optional[str] = None) -> bool:
    """
    Save link to database, or update existing link with a new name or url.

    If id is not provided, a new id will be generated, and inserted into the database.
    if id is provided, the link will be updated.

    Parameters:
        name (str): Link name.
        url (str): Link url.
        link_id (Optional[str]): Link id.

    Returns:
        bool: True if link was saved, False if link was not saved.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    if link_id is None:
        cur.execute("SELECT avg(rank) FROM links")
        rank = cur.fetchone()[0]
        if rank is None:
            rank = 1.0
        with con as cur:
            cur.execute(
                "INSERT INTO links (id, url, name, rank, accessed) VALUES (:id, :url, :name, :rank, :accessed)",
                {
                    "id": str(uuid4()),
                    "url": url,
                    "name": name,
                    "rank": rank,
                    "accessed": int(time()),
                },
            )
            return True
    else:
        with con as cur:
            cur.execute(
                "UPDATE links SET name = :name, url = :url WHERE id = :id",
                {
                    "id": link_id,
                    "name": name,
                    "url": url,
                },
            )
            return True


# Read config from data
def read_config() -> Dict[str, str]:
    """
    Read config from database.

    Returns:
        Dict[str, str]: Config name and value.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT name, value fROM metadata;")
    d = {row["name"]: row["value"] for row in cur.fetchall()}

    cur.execute("SELECT name, value FROM config")
    d |= {row["name"]: row["value"] for row in cur.fetchall()}
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


# Decrement the rank of all links when the sum of ranks is greater than the max rank.
def decrement_rank(max_rank: int = 1000) -> bool:
    """
    Decrement the rank of all links when the sum of ranks is greater than the max rank.

    Parameters:
        max_rank (int): Maximum rank.

    Returns:
        None: None.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT sum(rank) FROM links")
    total_rank = cur.fetchone()[0]
    # total_rank will be None if there are no links in the database.
    # Check if total_rank is greater than max_rank.
    if total_rank is not None and total_rank >= max_rank:
        print(
            "INFO:     Sum of all ranks is greater than max rank, decrementing all ranks."
        )
        cur.execute("UPDATE links SET rank = rank * 0.99")
        con.commit()
        return True
    return False


# Get application metadata from pyproject.toml file.
def get_app_metadata() -> Dict[str, str]:
    """
    Get application metadata from pyproject.toml file.

    Returns:
        Dict[str, str]: Application metadata.
    """
    with open(join(realpath(join(dirname(__file__), "../pyproject.toml")))) as f:
        f = f.read()
        return tomlkit.parse(f)["tool"]["poetry"]


# Search for links in the database.
def search_links(query: str) -> List[Dict[str, str]]:
    """
    Search for links in the database.

    Parameters:
        query (str): Search query.

    Returns:
        List[Dict[str, str]]: Links.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    cur = con.cursor()
    cur.execute(
        "SELECT id, name, url "
        "FROM links "
        "WHERE name LIKE :query OR url LIKE :query "
        "ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC",
        {"query": f"%{query}%"},
    )
    rows = cur.fetchall()
    con.close()
    return [{"id": row["id"], "name": row["name"], "url": row["url"]} for row in rows]
