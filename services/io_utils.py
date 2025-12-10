import argparse
import csv
import io
import json
import sqlite3
from pathlib import Path
from time import time
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
from uuid import uuid4

import services.db_utils as db_utils

EXPORT_FIELDS = ("id", "name", "url", "rank", "accessed", "tags")
VALID_FORMATS = {"csv", "json"}


def _normalize_format(format_name: str) -> str:
    normalized = (format_name or "").strip().lower()
    if normalized not in VALID_FORMATS:
        raise ValueError("Unsupported format. Choose 'csv' or 'json'.")
    return normalized


def _iter_link_rows(batch_size: int = 512) -> Iterator[Dict[str, object]]:
    """
    Yield each link row with its tags to keep memory usage predictable.
    """
    connection = sqlite3.connect(db_utils.db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT l.id, l.name, l.url, l.rank, l.accessed, t.name AS tag_name
        FROM links AS l
        LEFT JOIN tag_link_map AS tlm ON l.id = tlm.link_id
        LEFT JOIN tags AS t ON tlm.tag_id = t.id
        ORDER BY l.accessed DESC, l.id ASC, t.name ASC
        """
    )
    pending: Optional[Dict[str, object]] = None
    try:
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                link_id = row["id"]
                if pending and pending["id"] != link_id:
                    yield pending
                    pending = None
                if pending is None:
                    pending = {
                        "id": link_id,
                        "name": row["name"],
                        "url": row["url"],
                        "rank": float(row["rank"]),
                        "accessed": int(row["accessed"]),
                        "tags": [],
                    }
                tag_name = row["tag_name"]
                if tag_name and tag_name not in pending["tags"]:
                    pending["tags"].append(tag_name)
    finally:
        connection.close()
    if pending:
        yield pending


def _stream_json(rows: Iterable[Dict[str, object]]) -> Iterator[bytes]:
    yield b"["
    first = True
    for row in rows:
        chunk = json.dumps(
            {
                "id": row["id"],
                "name": row["name"],
                "url": row["url"],
                "rank": row["rank"],
                "accessed": row["accessed"],
                "tags": row.get("tags", []),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        if first:
            yield chunk
            first = False
        else:
            yield b"," + chunk
    yield b"]"


def _stream_csv(rows: Iterable[Dict[str, object]]) -> Iterator[bytes]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_FIELDS)
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    for row in rows:
        tags: List[str] = list(row.get("tags", []))
        writer.writerow(
            [
                row["id"],
                row["name"],
                row["url"],
                row["rank"],
                row["accessed"],
                ";".join(tags),
            ]
        )
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)


def _load_csv_rows(data: bytes) -> List[Dict[str, str]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV upload is missing a header row.")
    rows = list(reader)
    if not rows:
        raise ValueError("CSV upload does not contain any rows.")
    return rows


def _load_json_rows(data: bytes) -> List[Dict[str, object]]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("JSON upload could not be parsed.") from exc
    if not isinstance(payload, list):
        raise ValueError("JSON upload must be an array of link objects.")
    if not payload:
        raise ValueError("JSON upload does not contain any rows.")
    rows: List[Dict[str, object]] = []
    for idx, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"JSON row {idx} is not an object.")
        rows.append(item)
    return rows


def _normalize_tags(raw_tags: object) -> List[str]:
    tags: List[str] = []
    values: Sequence[str] = ()
    if isinstance(raw_tags, str):
        values = [part.strip() for part in raw_tags.split(";")]
    elif isinstance(raw_tags, Sequence):
        values = [str(part).strip() for part in raw_tags if str(part).strip()]
    for value in values:
        normalized = db_utils.normalize_tag(value)
        if normalized and normalized not in tags:
            tags.append(normalized)
    return tags


def _prepare_import_row(raw_row: Dict[str, object], index: int) -> Dict[str, object]:
    def require(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"Row {index}: {label} is required.")
        return cleaned

    link_id_value = str(raw_row.get("id") or "").strip()
    link_id = link_id_value or None
    name = require(str(raw_row.get("name", "")), "name")
    url = require(str(raw_row.get("url", "")), "url")

    rank_raw = raw_row.get("rank", 1.0)
    try:
        rank = float(rank_raw) if rank_raw not in ("", None) else 1.0
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {index}: rank must be numeric.") from exc

    accessed_raw = raw_row.get("accessed", int(time()))
    try:
        accessed = int(accessed_raw) if accessed_raw not in ("", None) else int(time())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {index}: accessed must be an integer timestamp.") from exc

    tags = _normalize_tags(raw_row.get("tags"))
    return {
        "id": link_id,
        "name": name,
        "url": url,
        "rank": rank,
        "accessed": accessed,
        "tags": tags,
    }


def _sync_tags(cursor: sqlite3.Cursor, link_id: str, tags: List[str]) -> None:
    cursor.execute(
        """
        SELECT t.id, t.name
        FROM tags AS t
        INNER JOIN tag_link_map tlm ON t.id = tlm.tag_id
        WHERE tlm.link_id = :link_id
        """,
        {"link_id": link_id},
    )
    existing_rows = cursor.fetchall()
    existing: Dict[str, str] = {row["name"]: row["id"] for row in existing_rows}
    target = set(tags)
    # Remove tags no longer present
    for current_name, tag_id in existing.items():
        if current_name in target:
            continue
        cursor.execute(
            "DELETE FROM tag_link_map WHERE tag_id = :tag_id AND link_id = :link_id",
            {"tag_id": tag_id, "link_id": link_id},
        )
        cursor.execute(
            "UPDATE tags SET count = (SELECT COUNT(*) FROM tag_link_map WHERE tag_id = :tag_id) WHERE id = :tag_id",
            {"tag_id": tag_id},
        )
        cursor.execute(
            "DELETE FROM tags WHERE id = :tag_id AND count = 0",
            {"tag_id": tag_id},
        )

    # Add or update requested tags
    for tag_name in tags:
        if tag_name in existing:
            continue
        cursor.execute("SELECT id FROM tags WHERE name = :name", {"name": tag_name})
        tag_row = cursor.fetchone()
        if tag_row:
            tag_id = tag_row["id"]
        else:
            tag_id = str(uuid4())
            cursor.execute(
                "INSERT INTO tags (id, name, count) VALUES (:id, :name, 0)",
                {"id": tag_id, "name": tag_name},
            )
        cursor.execute(
            "INSERT OR IGNORE INTO tag_link_map (tag_id, link_id) VALUES (:tag_id, :link_id)",
            {"tag_id": tag_id, "link_id": link_id},
        )
        cursor.execute(
            "UPDATE tags SET count = (SELECT COUNT(*) FROM tag_link_map WHERE tag_id = :tag_id) WHERE id = :tag_id",
            {"tag_id": tag_id},
        )


def _recalculate_tag_counts(cursor: sqlite3.Cursor) -> None:
    """
    Recalculate all tag counts based on actual tag_link_map entries.
    Ensures accuracy after bulk operations.
    """
    cursor.execute(
        """
        UPDATE tags
        SET count = (
            SELECT COUNT(*)
            FROM tag_link_map
            WHERE tag_id = tags.id
        )
        """
    )
    # Clean up orphaned tags with zero count
    cursor.execute("DELETE FROM tags WHERE count = 0")


def _upsert_link(cursor: sqlite3.Cursor, row: Dict[str, object]) -> Tuple[str, bool]:
    link_id = row["id"] or str(uuid4())
    cursor.execute("SELECT 1 FROM links WHERE id = :id", {"id": link_id})
    exists = cursor.fetchone() is not None
    params = {
        "id": link_id,
        "name": row["name"],
        "url": row["url"],
        "rank": row["rank"],
        "accessed": row["accessed"],
    }
    if exists:
        cursor.execute(
            "UPDATE links SET name = :name, url = :url, rank = :rank, accessed = :accessed WHERE id = :id",
            params,
        )
    else:
        cursor.execute(
            "INSERT INTO links (id, name, url, rank, accessed, expires_at) VALUES (:id, :name, :url, :rank, :accessed, NULL)",
            params,
        )
    return link_id, exists


def export_db_links(
    format_name: Optional[str] = None, batch_size: int = 512
) -> Iterator[Dict[str, object]] | Iterator[bytes]:
    """
    Export all links plus their tags.

    When no format is provided a generator of dictionaries is returned. Passing
    a supported format streams serialized bytes suitable for writing to disk or
    piping directly to a response.
    """
    if format_name is None:
        return _iter_link_rows(batch_size=batch_size)
    normalized = _normalize_format(format_name)
    rows = _iter_link_rows(batch_size=batch_size)
    if normalized == "json":
        return _stream_json(rows)
    return _stream_csv(rows)


def import_db_links(data: bytes, format_name: str) -> Dict[str, int]:
    """
    Import links from a CSV or JSON payload following the export schema.
    Skips rows that would violate unique constraints (duplicate name/URL).
    """
    if not data:
        raise ValueError("Import payload is empty.")
    normalized = _normalize_format(format_name)
    raw_rows = _load_json_rows(data) if normalized == "json" else _load_csv_rows(data)
    connection = sqlite3.connect(db_utils.db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    created = 0
    updated = 0
    skipped = 0
    try:
        for index, raw_row in enumerate(raw_rows, start=1):
            try:
                prepared = _prepare_import_row(raw_row, index)
                link_id, existed = _upsert_link(cursor, prepared)
                _sync_tags(cursor, link_id, prepared["tags"])
                if existed:
                    updated += 1
                else:
                    created += 1
            except sqlite3.IntegrityError:
                # Skip rows that would violate unique constraints (duplicate name/URL)
                skipped += 1
                continue
        # Recalculate all tag counts to ensure accuracy after bulk changes
        _recalculate_tag_counts(cursor)
        connection.commit()
    finally:
        connection.close()
    return {"created": created, "updated": updated, "skipped": skipped}


def write_export_file(format_name: str, destination: Path, batch_size: int = 512) -> Path:
    """
    Write the requested export format to the provided destination path.
    """
    normalized = _normalize_format(format_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = _iter_link_rows(batch_size=batch_size)
    stream = _stream_json(rows) if normalized == "json" else _stream_csv(rows)
    with destination.open("wb") as handle:
        for chunk in stream:
            handle.write(chunk)
    return destination


def _cli():
    parser = argparse.ArgumentParser(description="StartPage link export helper.")
    parser.add_argument(
        "format",
        nargs="?",
        default="csv",
        choices=sorted(VALID_FORMATS),
        help="Export format.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Destination file. Defaults to startpage-links.<format>.",
    )
    args = parser.parse_args()
    output = args.output or Path(f"startpage-links.{args.format}")
    write_export_file(args.format, output)
    print(f"Wrote {output}")


if __name__ == "__main__":
    _cli()
