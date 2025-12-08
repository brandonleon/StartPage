import re
import sqlite3
from sqlite3 import IntegrityError
from os import mkdir
from os.path import dirname, isdir, join, realpath
from time import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

import timeago
import tomlkit

from services import app_config

db_path = realpath(join(dirname(__file__), "..", "data", "links.db"))

TAG_WHITESPACE_PATTERN = re.compile(r"\s+")
TAG_INVALID_CHARS_PATTERN = re.compile(r"[^a-z0-9-]")


class DuplicateLinkError(Exception):
    """Raised when inserting or updating a link violates the unique name/url constraint."""

    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        super().__init__(f"Duplicate {field}: {value}")


def normalize_tag(tag_name: str) -> str:
    """
    Canonicalize user-provided tag strings.

    Lowercases text, converts whitespace to hyphens, removes everything that
    isn't [a-z0-9-], and collapses redundant separators so persisted tags
    contain only the allowed characters.
    """
    cleaned = tag_name.lower()
    cleaned = TAG_WHITESPACE_PATTERN.sub("-", cleaned)
    cleaned = TAG_INVALID_CHARS_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned.strip("-")


def _ensure_expires_column() -> None:
    """Ensure the links table includes the expires_at column and supporting index."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        cur.execute("PRAGMA table_info(links);")
        columns = {row[1] for row in cur.fetchall()}
        if "expires_at" not in columns:
            cur.execute("ALTER TABLE links ADD COLUMN expires_at INTEGER")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_expires_at ON links(expires_at)"
        )
        con.commit()
    finally:
        con.close()


def purge_expired_links(now: Optional[int] = None) -> int:
    """
    Delete links whose expires_at timestamp is in the past.

    Returns:
        int: The number of removed rows.
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    if now is None:
        now = int(time())
    cur.execute(
        "DELETE FROM links WHERE expires_at IS NOT NULL AND expires_at <= :now",
        {"now": now},
    )
    removed = cur.rowcount or 0
    con.commit()
    con.close()
    return removed


def format_expires_in(expires_at: Optional[int], now: Optional[int] = None) -> Optional[str]:
    """Return a short description of how long remains until expiration."""
    if expires_at is None:
        return None
    if now is None:
        now = int(time())
    seconds_remaining = expires_at - now
    if seconds_remaining <= 0:
        return "less than a minute"
    units = (
        ("day", 86400),
        ("hour", 3600),
        ("minute", 60),
    )
    for label, unit_seconds in units:
        if seconds_remaining >= unit_seconds:
            value = seconds_remaining // unit_seconds
            suffix = "" if value == 1 else "s"
            return f"{value} {label}{suffix}"
    return "less than a minute"


def _serialize_link_row(row: sqlite3.Row, now: Optional[int] = None) -> Dict[str, Any]:
    """
    Convert a sqlite row into the dictionary structure consumed throughout the app.
    """
    if now is None:
        now = int(time())
    expires_at = row["expires_at"]
    expires_in_seconds = None
    if expires_at is not None:
        expires_in_seconds = max(0, expires_at - now)
    return dict(
        id=row["id"],
        url=row["url"],
        name=row["name"],
        rank=row["rank"],
        accessed=timeago.format(row["accessed"]),
        tags=get_tags_for_link(row["id"]),
        expires_at=expires_at,
        expires_in=format_expires_in(expires_at, now),
        expires_in_seconds=expires_in_seconds,
        is_temporary=expires_at is not None,
    )


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
    purge_expired_links()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT id, name, url, expires_at fROM links WHERE id = :link_id",
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


def find_link_by_url(url: str) -> Optional[Dict[str, Any]]:
    """Return a serialized link that matches the provided URL, if any."""
    return _find_link_by_column("url", url)


def find_link_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Return a serialized link that matches the provided name, if any."""
    return _find_link_by_column("name", name)


def _find_link_by_column(column: str, value: str) -> Optional[Dict[str, Any]]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if column not in {"name", "url"}:
        raise ValueError("Unsupported lookup column")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        f"SELECT id, name, url, rank, accessed, expires_at FROM links WHERE lower({column}) = lower(:value) LIMIT 1",
        {"value": normalized},
    )
    row = cur.fetchone()
    con.close()
    if row is None:
        return None
    return _serialize_link_row(row)


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
    purge_expired_links()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    cur = con.cursor()
    if batch is None:
        batch = app_config.get_runtime_config().frecency.batch_size
    offset = page * batch
    cur.execute(
        "SELECT id, url, name, rank, accessed, expires_at fROM links "
        "ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC "
        "LIMIT :page, :batch;",
        {"page": offset, "batch": batch},
    )
    rows = cur.fetchall()

    now = int(time())
    links = [_serialize_link_row(row, now) for row in rows]
    con.close()
    return links


def get_temp_link_config() -> Dict[str, int | bool]:
    """Return runtime temp-link settings."""
    temp_config = app_config.get_runtime_config().temp_links
    return {
        "enabled": temp_config.enabled,
        "default_ttl_hours": temp_config.default_ttl_hours,
        "max_custom_hours": temp_config.max_custom_hours,
        "purge_interval_seconds": temp_config.purge_interval_seconds,
    }


def update_temp_link_config(
    enabled: bool,
    default_ttl_hours: int,
    max_custom_hours: int,
    purge_interval_seconds: int,
) -> Dict[str, int | bool]:
    """Persist validated temporary-link settings and return the stored values."""
    config = app_config.update_temp_link_settings(
        enabled,
        default_ttl_hours,
        max_custom_hours,
        purge_interval_seconds,
    )
    temp_config = config.temp_links
    return {
        "enabled": temp_config.enabled,
        "default_ttl_hours": temp_config.default_ttl_hours,
        "max_custom_hours": temp_config.max_custom_hours,
        "purge_interval_seconds": temp_config.purge_interval_seconds,
    }


def get_count() -> Dict[str, int]:
    """Return the number of links currently stored in the database."""
    purge_expired_links()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM links;")
    total_links = cur.fetchone()[0] or 0
    con.close()
    return {"count": total_links}


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
    app_config.ensure_config_file()
    _ensure_expires_column()


# add link to database
def save_link(
    name: str,
    url: str,
    link_id: Optional[str] = None,
    expires_at: Optional[int] = None,
) -> str:
    """
    Save link to database, or update existing link with a new name or url.

    If id is not provided, a new id will be generated, and inserted into the database.
    if id is provided, the link will be updated.

    Parameters:
        name (str): Link name.
        url (str): Link url.
        link_id (Optional[str]): Link id.
        expires_at (Optional[int]): Expiration timestamp, or None for permanent links.

    Returns:
        str: The link id (generated if new, or the provided id if updating).
    """
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        if link_id is None:
            cur.execute("SELECT avg(rank) FROM links")
            rank = cur.fetchone()[0]
            if rank is None:
                rank = 1.0
            new_id = str(uuid4())
            cur.execute(
                "INSERT INTO links (id, url, name, rank, accessed, expires_at) VALUES (:id, :url, :name, :rank, :accessed, :expires_at)",
                {
                    "id": new_id,
                    "url": url,
                    "name": name,
                    "rank": rank,
                    "accessed": int(time()),
                    "expires_at": expires_at,
                },
            )
            con.commit()
            return new_id
        else:
            cur.execute(
                "UPDATE links SET name = :name, url = :url, expires_at = :expires_at WHERE id = :id",
                {
                    "id": link_id,
                    "name": name,
                    "url": url,
                    "expires_at": expires_at,
                },
            )
            con.commit()
            return link_id
    except IntegrityError as exc:
        con.rollback()
        raise _interpret_integrity_error(exc, name, url) from exc
    finally:
        con.close()


def _interpret_integrity_error(exc: IntegrityError, name: str, url: str) -> DuplicateLinkError:
    message = str(exc).lower()
    if "links.name" in message:
        return DuplicateLinkError("name", name)
    if "links.url" in message or "links.id" in message:
        return DuplicateLinkError("url", url)
    return DuplicateLinkError("url", url)


# Read metadata from database
def read_metadata() -> Dict[str, str]:
    """
    Read metadata key/value pairs from the database.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT name, value fROM metadata;")
    d = {row["name"]: row["value"] for row in cur.fetchall()}
    con.close()
    return d


def get_frecency_config() -> Dict[str, int]:
    """Return the current batch size and max rank thresholds."""
    frecency = app_config.get_runtime_config().frecency
    return {"batch_size": frecency.batch_size, "max_rank": frecency.max_rank}


def update_frecency_config(batch_size: int, max_rank: int) -> Dict[str, int]:
    """Persist validated frecency settings and return the stored values."""
    updated = app_config.update_frecency_settings(batch_size, max_rank).frecency
    return {"batch_size": updated.batch_size, "max_rank": updated.max_rank}


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
        max_rank = app_config.get_runtime_config().frecency.max_rank
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
def search_links(query: str) -> List[Dict[str, Any]]:
    """
    Search for links in the database.

    Parameters:
        query (str): Search query.

    Returns:
        List[Dict[str, str]]: Links with their tags.
    """
    purge_expired_links()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    cur = con.cursor()
    cur.execute(
        "SELECT id, name, url, rank, accessed, expires_at "
        "FROM links "
        "WHERE name LIKE :query OR url LIKE :query "
        "ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC",
        {"query": f"%{query}%"},
    )
    rows = cur.fetchall()
    con.close()

    now = int(time())
    return [_serialize_link_row(row, now) for row in rows]


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
    cur.execute(
        "SELECT id, name, count FROM tags "
        "ORDER BY count DESC, name ASC"
    )
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
    tag_name = normalize_tag(tag_name)
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


def rename_tag(tag_id: str, new_name: str) -> bool:
    """
    Rename a tag. Merges with an existing tag if the target name already exists.

    Parameters:
        tag_id (str): Tag id to rename.
        new_name (str): Desired tag name.

    Returns:
        bool: True if the tag was updated or merged, False otherwise.
    """
    new_name = normalize_tag(new_name)
    if not new_name:
        return False

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("SELECT id FROM tags WHERE id = :tag_id", {"tag_id": tag_id})
    current = cur.fetchone()
    if not current:
        con.close()
        return False

    cur.execute("SELECT id FROM tags WHERE name = :name", {"name": new_name})
    existing = cur.fetchone()

    if existing and existing["id"] == tag_id:
        con.close()
        return True

    if existing:
        existing_id = existing["id"]
        cur.execute(
            "INSERT OR IGNORE INTO tag_link_map (tag_id, link_id) "
            "SELECT :new_id, link_id FROM tag_link_map WHERE tag_id = :old_id",
            {"new_id": existing_id, "old_id": tag_id},
        )
        cur.execute("DELETE FROM tag_link_map WHERE tag_id = :old_id", {"old_id": tag_id})
        cur.execute("DELETE FROM tags WHERE id = :old_id", {"old_id": tag_id})
        cur.execute(
            "UPDATE tags SET count = (SELECT COUNT(*) FROM tag_link_map WHERE tag_id = :tag_id) WHERE id = :tag_id",
            {"tag_id": existing_id},
        )
    else:
        cur.execute(
            "UPDATE tags SET name = :name WHERE id = :tag_id",
            {"name": new_name, "tag_id": tag_id},
        )
        cur.execute(
            "UPDATE tags SET count = (SELECT COUNT(*) FROM tag_link_map WHERE tag_id = :tag_id) WHERE id = :tag_id",
            {"tag_id": tag_id},
        )

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
    purge_expired_links()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if batch is None:
        batch = app_config.get_runtime_config().frecency.batch_size
    offset = page * batch

    cur.execute(
        "SELECT l.id, l.url, l.name, l.rank, l.accessed, l.expires_at "
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

    now = int(time())
    return [_serialize_link_row(row, now) for row in rows]


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
    frecency = app_config.get_runtime_config().frecency
    batch_size = frecency.batch_size
    max_rank = frecency.max_rank

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
