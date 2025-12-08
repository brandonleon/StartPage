import sqlite3
from os import mkdir
from os.path import dirname, isdir, join, realpath
from time import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

import timeago
import tomlkit

db_path = realpath(join(dirname(__file__), "..", "data", "links.db"))

DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_RANK = 1000


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
        "SELECT id, name, url fROM links WHERE id = :link_id",
        {"link_id": link_id},
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
def get_links(page: int = 0, batch: Optional[int] = None) -> List[dict]:
    """
    Get links in batches of n, defaulting to the configured batch size.

    Parameters:
        page (int): Page number.
        batch (int | None): Number of links to return per page.

    Returns:
        list: List of links with their tags.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    cur = con.cursor()
    if batch is None:
        batch = _get_batch_size(cur)
    offset = page * batch
    cur.execute(
        "SELECT id, url, name, rank, accessed fROM links "
        "ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC "
        "LIMIT :page, :batch;",
        {"page": offset, "batch": batch},
    )
    rows = cur.fetchall()

    links = []
    for row in rows:
        link_id = row["id"]
        # Get tags for this link
        tags = get_tags_for_link(link_id)
        links.append(
            dict(
                id=link_id,
                url=row["url"],
                name=row["name"],
                rank=row["rank"],
                accessed=timeago.format(row["accessed"]),
                tags=tags,
            )
        )

    con.close()
    return links


def _get_batch_size(cur: sqlite3.Cursor) -> int:
    """
    Helper to read the configured batch size from the config table.
    Defaults to 20 when the setting is missing or invalid.
    """
    cur.execute(
        "SELECT value FROM config WHERE name = 'batch' LIMIT 1;"
    )
    row = cur.fetchone()
    try:
        return max(1, int(row[0])) if row and row[0] is not None else DEFAULT_BATCH_SIZE
    except (TypeError, ValueError):
        return DEFAULT_BATCH_SIZE


def _get_max_rank(cur: sqlite3.Cursor) -> int:
    """Read the max_rank pruning limit stored in config."""
    cur.execute(
        "SELECT value FROM config WHERE name = 'max_rank' LIMIT 1;"
    )
    row = cur.fetchone()
    try:
        return max(1, int(row[0])) if row and row[0] is not None else DEFAULT_MAX_RANK
    except (TypeError, ValueError):
        return DEFAULT_MAX_RANK


def _ensure_config_defaults() -> None:
    """Ensure new config rows exist for deployments created before this release."""
    defaults = {
        "batch": str(DEFAULT_BATCH_SIZE),
        "max_rank": str(DEFAULT_MAX_RANK),
    }
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    for name, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO config (id, name, value) VALUES (:id, :name, :value)",
            {"id": str(uuid4()), "name": name, "value": value},
        )
    con.commit()
    con.close()


def get_count() -> Dict[str, int]:
    """
    Return the number of links in the database and the total number of pages.

    The page count is derived from the configured batch size.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM links;")
    total_links = cur.fetchone()[0] or 0
    batch_size = _get_batch_size(cur)
    con.close()

    pages = (total_links + batch_size - 1) // batch_size
    return {"count": total_links, "pages": pages}


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
        cur.execute(
            "DELETE FROM links WHERE id = :link_id", {"link_id": link_id}
        )
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
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='links';"
    )
    result = cur.fetchone()
    if result is None:
        with open(
            join(realpath(join(dirname(__file__), "../sql_scripts", schema))),
            "r",
        ) as sql_file:
            cur.executescript(sql_file.read())
            con.commit()
    con.close()
    _ensure_config_defaults()


# add link to database
def save_link(name: str, url: str, link_id: Optional[str] = None) -> str:
    """
    Save link to database, or update existing link with a new name or url.

    If id is not provided, a new id will be generated, and inserted into the database.
    if id is provided, the link will be updated.

    Parameters:
        name (str): Link name.
        url (str): Link url.
        link_id (Optional[str]): Link id.

    Returns:
        str: The link id (generated if new, or the provided id if updating).
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    if link_id is None:
        cur.execute("SELECT avg(rank) FROM links")
        rank = cur.fetchone()[0]
        if rank is None:
            rank = 1.0
        new_id = str(uuid4())
        with con as cur:
            cur.execute(
                "INSERT INTO links (id, url, name, rank, accessed) VALUES (:id, :url, :name, :rank, :accessed)",
                {
                    "id": new_id,
                    "url": url,
                    "name": name,
                    "rank": rank,
                    "accessed": int(time()),
                },
            )
            return new_id
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
            return link_id


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


def get_frecency_config() -> Dict[str, int]:
    """Return the current batch size and max rank thresholds."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    batch_size = _get_batch_size(cur)
    max_rank = _get_max_rank(cur)
    con.close()
    return {"batch_size": batch_size, "max_rank": max_rank}


def _upsert_config_value(cur: sqlite3.Cursor, name: str, value: str) -> None:
    cur.execute(
        "UPDATE config SET value = :value WHERE name = :name",
        {"name": name, "value": value},
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO config (id, name, value) VALUES (:id, :name, :value)",
            {"id": str(uuid4()), "name": name, "value": value},
        )


def update_frecency_config(batch_size: int, max_rank: int) -> Dict[str, int]:
    """Persist validated frecency settings and return the stored values."""
    batch_size = max(1, batch_size)
    max_rank = max(1, max_rank)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    _upsert_config_value(cur, "batch", str(batch_size))
    _upsert_config_value(cur, "max_rank", str(max_rank))
    con.commit()
    con.close()
    return {"batch_size": batch_size, "max_rank": max_rank}


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
        join(
            realpath(
                join(dirname(__file__), "../sql_scripts", migration_script)
            )
        ),
        "r",
    ) as sql_file:
        cur.executescript(sql_file.read())
        con.commit()


# Decrement the rank of all links when the sum of ranks is greater than the max rank.
def decrement_rank(max_rank: Optional[int] = None) -> None:
    """
    Decrement the rank of all links when the sum of ranks is greater than the max rank.

    Parameters:
        max_rank (int): Maximum rank.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    if max_rank is None:
        max_rank = _get_max_rank(cur)
    cur.execute("SELECT sum(rank) FROM links")
    total_rank = cur.fetchone()[0]
    # total_rank will be None if there are no links in the database.
    # Check if total_rank is greater than max_rank,
    # If so, remove any items with a rank below 1 and decrement the rest by 1%.
    if total_rank is not None and total_rank >= max_rank:
        print(
            "INFO:     Sum of all ranks is greater than max rank, decrementing all ranks."
        )
        cur.executescript(
            "DELETE from links WHERE rank < 1; UPDATE links SET rank = rank * 0.99;"
        )
        con.commit()


# Get application metadata from pyproject.toml file.
def get_app_metadata() -> Dict[str, str]:
    """
    Get application metadata from pyproject.toml file.

    Returns:
        Dict[str, str]: Application metadata.
    """
    with open(
        join(realpath(join(dirname(__file__), "../pyproject.toml")))
    ) as f:
        project = tomlkit.parse(f.read())["project"]
        return {"name": project["name"], "version": project["version"]}


# Search for links in the database.
def search_links(query: str) -> List[Dict[str, str]]:
    """
    Search for links in the database.

    Parameters:
        query (str): Search query.

    Returns:
        List[Dict[str, str]]: Links with their tags.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    cur = con.cursor()
    cur.execute(
        "SELECT id, name, url, rank, accessed "
        "FROM links "
        "WHERE name LIKE :query OR url LIKE :query "
        "ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC",
        {"query": f"%{query}%"},
    )
    rows = cur.fetchall()
    con.close()

    links = []
    for row in rows:
        link_id = row["id"]
        tags = get_tags_for_link(link_id)
        links.append(
            {
                "id": link_id,
                "name": row["name"],
                "url": row["url"],
                "rank": row["rank"],
                "accessed": timeago.format(row["accessed"]),
                "tags": tags,
            }
        )
    return links


# Tag management functions
def get_all_tags() -> List[Dict[str, Any]]:
    """
    Get all tags with their counts.

    Returns:
        List[Dict[str, Any]]: List of tags with id, name, and count.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT id, name, count FROM tags ORDER BY name ASC")
    rows = cur.fetchall()
    con.close()
    return [{"id": row["id"], "name": row["name"], "count": row["count"]} for row in rows]


def get_tags_for_link(link_id: str) -> List[Dict[str, str]]:
    """
    Get all tags for a specific link.

    Parameters:
        link_id (str): Link id.

    Returns:
        List[Dict[str, str]]: List of tags with id and name.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT t.id, t.name FROM tags t "
        "INNER JOIN tag_link_map tlm ON t.id = tlm.tag_id "
        "WHERE tlm.link_id = :link_id "
        "ORDER BY t.name ASC",
        {"link_id": link_id},
    )
    rows = cur.fetchall()
    con.close()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


def add_tag_to_link(link_id: str, tag_name: str) -> bool:
    """
    Add a tag to a link. Creates the tag if it doesn't exist.

    Parameters:
        link_id (str): Link id.
        tag_name (str): Tag name.

    Returns:
        bool: True if tag was added successfully.
    """
    tag_name = tag_name.strip().lower()
    if not tag_name:
        return False

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Get or create tag
    cur.execute("SELECT id FROM tags WHERE name = :name", {"name": tag_name})
    tag_row = cur.fetchone()

    if tag_row:
        tag_id = tag_row["id"]
    else:
        tag_id = str(uuid4())
        cur.execute(
            "INSERT INTO tags (id, name, count) VALUES (:id, :name, 0)",
            {"id": tag_id, "name": tag_name},
        )

    # Check if link-tag mapping already exists
    cur.execute(
        "SELECT 1 FROM tag_link_map WHERE tag_id = :tag_id AND link_id = :link_id",
        {"tag_id": tag_id, "link_id": link_id},
    )

    if not cur.fetchone():
        # Add mapping and update count
        cur.execute(
            "INSERT INTO tag_link_map (tag_id, link_id) VALUES (:tag_id, :link_id)",
            {"tag_id": tag_id, "link_id": link_id},
        )
        cur.execute(
            "UPDATE tags SET count = (SELECT COUNT(*) FROM tag_link_map WHERE tag_id = :tag_id) WHERE id = :tag_id",
            {"tag_id": tag_id},
        )

    con.commit()
    con.close()
    return True


def remove_tag_from_link(link_id: str, tag_id: str) -> bool:
    """
    Remove a tag from a link.

    Parameters:
        link_id (str): Link id.
        tag_id (str): Tag id.

    Returns:
        bool: True if tag was removed successfully.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute(
        "DELETE FROM tag_link_map WHERE tag_id = :tag_id AND link_id = :link_id",
        {"tag_id": tag_id, "link_id": link_id},
    )

    # Update tag count
    cur.execute(
        "UPDATE tags SET count = (SELECT COUNT(*) FROM tag_link_map WHERE tag_id = :tag_id) WHERE id = :tag_id",
        {"tag_id": tag_id},
    )

    # Delete tag if count is 0
    cur.execute("DELETE FROM tags WHERE id = :tag_id AND count = 0", {"tag_id": tag_id})

    con.commit()
    con.close()
    return True


def delete_tag(tag_id: str) -> bool:
    """
    Delete a tag completely (removes all link associations).

    Parameters:
        tag_id (str): Tag id.

    Returns:
        bool: True if tag was deleted successfully.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("DELETE FROM tag_link_map WHERE tag_id = :tag_id", {"tag_id": tag_id})
    cur.execute("DELETE FROM tags WHERE id = :tag_id", {"tag_id": tag_id})

    con.commit()
    con.close()
    return True


def get_links_by_tag(tag_name: str, page: int = 0, batch: Optional[int] = None) -> List[dict]:
    """
    Get links filtered by tag name, sorted by frecency.

    Parameters:
        tag_name (str): Tag name to filter by.
        page (int): Page number.
        batch (int | None): Number of links to return per page.

    Returns:
        list: List of links with the specified tag, including all their tags.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if batch is None:
        batch = _get_batch_size(cur)
    offset = page * batch

    cur.execute(
        "SELECT l.id, l.url, l.name, l.rank, l.accessed "
        "FROM links l "
        "INNER JOIN tag_link_map tlm ON l.id = tlm.link_id "
        "INNER JOIN tags t ON tlm.tag_id = t.id "
        "WHERE t.name = :tag_name "
        "ORDER BY 10000 * l.rank * (3.75/((0.0001 * (strftime('%s','now') - l.accessed) + 1) + 0.25)) DESC "
        "LIMIT :page, :batch",
        {"tag_name": tag_name, "page": offset, "batch": batch},
    )
    rows = cur.fetchall()
    con.close()

    links = []
    for row in rows:
        link_id = row["id"]
        tags = get_tags_for_link(link_id)
        links.append(
            dict(
                id=link_id,
                url=row["url"],
                name=row["name"],
                rank=row["rank"],
                accessed=timeago.format(row["accessed"]),
                tags=tags,
            )
        )

    return links


# Get database statistics.
def get_stats() -> Dict[str, Any]:
    """
    Get database statistics including rank stats, access patterns, and more.

    Returns:
        Dict[str, Any]: Dictionary containing various database statistics.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Rank statistics
    cur.execute(
        "SELECT "
        "SUM(rank) as sum_rank, "
        "AVG(rank) as avg_rank, "
        "MIN(rank) as min_rank, "
        "MAX(rank) as max_rank, "
        "COUNT(*) as total_links "
        "FROM links"
    )
    rank_stats = cur.fetchone()

    # Access pattern statistics
    cur.execute(
        "SELECT "
        "MIN(accessed) as oldest_access, "
        "MAX(accessed) as newest_access "
        "FROM links"
    )
    access_stats = cur.fetchone()

    # Top 10 most frequently accessed links
    cur.execute(
        "SELECT id, name, url, rank, accessed "
        "FROM links "
        "ORDER BY rank DESC "
        "LIMIT 10"
    )
    top_links = cur.fetchall()

    # Top 10 most recently accessed links
    cur.execute(
        "SELECT id, name, url, rank, accessed "
        "FROM links "
        "ORDER BY accessed DESC "
        "LIMIT 10"
    )
    recent_links = cur.fetchall()

    # Least accessed links (bottom 10 by rank)
    cur.execute(
        "SELECT id, name, url, rank, accessed "
        "FROM links "
        "ORDER BY rank ASC "
        "LIMIT 10"
    )
    least_links = cur.fetchall()

    # Get batch size configuration
    batch_size = _get_batch_size(cur)
    max_rank = _get_max_rank(cur)

    con.close()

    return {
        "rank_stats": {
            "sum": rank_stats["sum_rank"] or 0,
            "avg": rank_stats["avg_rank"] or 0,
            "min": rank_stats["min_rank"] or 0,
            "max": rank_stats["max_rank"] or 0,
            "total_links": rank_stats["total_links"] or 0,
        },
        "access_stats": {
            "oldest_access": access_stats["oldest_access"],
            "newest_access": access_stats["newest_access"],
            "oldest_timeago": timeago.format(access_stats["oldest_access"]) if access_stats["oldest_access"] else "N/A",
            "newest_timeago": timeago.format(access_stats["newest_access"]) if access_stats["newest_access"] else "N/A",
        },
        "top_links": [
            {
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "rank": row["rank"],
                "accessed": timeago.format(row["accessed"]),
            }
            for row in top_links
        ],
        "recent_links": [
            {
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "rank": row["rank"],
                "accessed": timeago.format(row["accessed"]),
            }
            for row in recent_links
        ],
        "least_links": [
            {
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "rank": row["rank"],
                "accessed": timeago.format(row["accessed"]),
            }
            for row in least_links
        ],
        "config": {
            "batch_size": batch_size,
            "max_rank": max_rank,
        },
    }
