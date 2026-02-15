# StartPage Performance Recommendations

This document outlines recommended performance improvements for the StartPage application based on a code review conducted on December 18, 2025.

## 1. Database Indexing Improvements

The application performs frequent searches and sorts on several columns, but only has an index on `expires_at`. Adding these indexes would significantly speed up query performance:

```sql
-- Add indexes for frequently queried columns
CREATE INDEX IF NOT EXISTS idx_links_name ON links(name);
CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);
CREATE INDEX IF NOT EXISTS idx_links_rank ON links(rank);
CREATE INDEX IF NOT EXISTS idx_links_accessed ON links(accessed);
```

**Benefits:**
- Faster search operations
- Improved sorting performance
- Reduced query execution time

## 2. Database Connection Pooling

The current implementation creates a new database connection for each request, which is inefficient under high load. Implementing connection pooling would reuse connections:

```python
# Add to services/db_utils.py
from functools import wraps
import contextlib

_connection_pool = []
_MAX_POOL_SIZE = 5

@contextlib.contextmanager
def get_db_connection():
    """Get a connection from the pool or create a new one if needed."""
    if _connection_pool:
        conn = _connection_pool.pop()
    else:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        yield conn
    finally:
        if len(_connection_pool) < _MAX_POOL_SIZE:
            _connection_pool.append(conn)
        else:
            conn.close()
```

**Benefits:**
- Reduced connection overhead
- Better resource utilization
- Improved request handling under load

## 3. Query Optimization for Frecency Calculation

The frecency calculation is performed in SQL for every query, which is computationally expensive:

```sql
ORDER BY 10000 * rank * (3.75/((0.0001 * (strftime('%s','now') - accessed) + 1) + 0.25)) DESC
```

**Recommendations:**
1. Pre-calculate frecency values during off-peak times
2. Simplify the formula if possible
3. Create a materialized view or cache for frequently accessed queries
4. Consider adding a dedicated frecency column that's updated periodically

## 4. Batch Processing for Tag Operations

When handling tags, especially during bulk operations, the code makes multiple database calls. Implementing batch processing would reduce database overhead:

```python
def batch_add_tags_to_links(link_ids, tag_names):
    """Add multiple tags to multiple links in a single transaction."""
    con = _get_connection()
    cur = con.cursor()
    try:
        # Prepare tag IDs (create if needed)
        tag_ids = {}
        for tag_name in tag_names:
            normalized = normalize_tag(tag_name)
            if not normalized:
                continue
                
            # Get or create tag
            cur.execute(
                "SELECT id FROM tags WHERE name = ?",
                (normalized,)
            )
            result = cur.fetchone()
            if result:
                tag_ids[normalized] = result[0]
            else:
                tag_id = str(uuid4())
                cur.execute(
                    "INSERT INTO tags (id, name, count) VALUES (?, ?, 0)",
                    (tag_id, normalized)
                )
                tag_ids[normalized] = tag_id
        
        # Batch insert mappings
        mappings = []
        for link_id in link_ids:
            for tag_name, tag_id in tag_ids.items():
                mappings.append((tag_id, link_id))
                
        cur.executemany(
            "INSERT OR IGNORE INTO tag_link_map (tag_id, link_id) VALUES (?, ?)",
            mappings
        )
        
        # Update counts in a single query
        cur.execute("""
            UPDATE tags
            SET count = (
                SELECT COUNT(*)
                FROM tag_link_map
                WHERE tag_link_map.tag_id = tags.id
            )
        """)
        
        con.commit()
    except Exception as e:
        con.rollback()
        raise e
    finally:
        con.close()
```

**Benefits:**
- Reduced number of database transactions
- Improved performance for bulk operations
- Lower overhead when adding multiple tags

## 5. Implement Caching

Add caching for frequently accessed data:

```python
# Add to services/db_utils.py
import functools
import time

# Simple time-based cache decorator
def cache_result(seconds=60):
    def decorator(func):
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            current_time = time.time()
            if key in cache:
                result, timestamp = cache[key]
                if current_time - timestamp < seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            return result
        
        return wrapper
    
    return decorator

# Apply to frequently called functions
@cache_result(seconds=300)  # Cache for 5 minutes
def get_all_tags():
    # Existing implementation
```

**Candidates for caching:**
- `get_all_tags()`
- `get_frecency_config()`
- `get_temp_link_config()`
- `get_app_metadata()`
- `get_stats()`

## 6. Optimize Search Functionality

The current search function performs a simple LIKE query, which becomes inefficient with large datasets:

```python
"WHERE name LIKE :query OR url LIKE :query"
```

**Recommendations:**
1. Implement full-text search using SQLite's FTS5 extension:

```sql
-- Create a virtual FTS5 table
CREATE VIRTUAL TABLE links_fts USING fts5(
    id, 
    name, 
    url, 
    content='links', 
    content_rowid='id'
);

-- Create triggers to keep it in sync
CREATE TRIGGER links_ai AFTER INSERT ON links BEGIN
  INSERT INTO links_fts(rowid, name, url) VALUES (new.id, new.name, new.url);
END;

CREATE TRIGGER links_ad AFTER DELETE ON links BEGIN
  INSERT INTO links_fts(links_fts, rowid, name, url) VALUES('delete', old.id, old.name, old.url);
END;

CREATE TRIGGER links_au AFTER UPDATE ON links BEGIN
  INSERT INTO links_fts(links_fts, rowid, name, url) VALUES('delete', old.id, old.name, old.url);
  INSERT INTO links_fts(rowid, name, url) VALUES (new.id, new.name, new.url);
END;
```

2. Use the FTS5 table for searches:

```python
def search_links_optimized(query: str) -> List[Dict[str, Any]]:
    """Search for links using the FTS5 index."""
    purge_expired_links()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    
    cur = con.cursor()
    cur.execute(
        """
        SELECT l.id, l.name, l.url, l.rank, l.accessed, l.expires_at
        FROM links_fts AS fts
        JOIN links AS l ON fts.rowid = l.id
        WHERE fts.name MATCH :query OR fts.url MATCH :query
        ORDER BY 10000 * l.rank * (3.75/((0.0001 * (strftime('%s','now') - l.accessed) + 1) + 0.25)) DESC
        """,
        {"query": query},
    )
    rows = cur.fetchall()
    con.close()
    
    now = int(time())
    return [_serialize_link_row(row, now) for row in rows]
```

## 7. Pagination Optimization

The current pagination implementation loads all results for a page at once. For large datasets, cursor-based pagination would be more efficient:

```python
def get_links_cursor_based(cursor_id=None, limit=None):
    """Get links using cursor-based pagination for better performance."""
    purge_expired_links()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    
    cur = con.cursor()
    if limit is None:
        limit = app_config.get_runtime_config().frecency.batch_size
    
    if cursor_id:
        # Get next batch after the cursor
        cur.execute(
            """
            SELECT id, url, name, rank, accessed, expires_at FROM links 
            WHERE id > :cursor_id
            ORDER BY id ASC
            LIMIT :limit
            """,
            {"cursor_id": cursor_id, "limit": limit},
        )
    else:
        # Get first batch
        cur.execute(
            """
            SELECT id, url, name, rank, accessed, expires_at FROM links 
            ORDER BY id ASC
            LIMIT :limit
            """,
            {"limit": limit},
        )
    
    rows = cur.fetchall()
    now = int(time())
    links = [_serialize_link_row(row, now) for row in rows]
    
    # Return the last ID as the next cursor
    next_cursor = links[-1]["id"] if links else None
    
    con.close()
    return {"links": links, "next_cursor": next_cursor}
```

## 8. Async Processing for Background Tasks

Move expensive operations to background tasks:

```python
# In main.py
@app.post("/add_link")
async def add_link(background_tasks: BackgroundTasks, ...):
    # Quick operations for immediate response
    link_id = db_utils.save_link_minimal(name, url)
    
    # Move expensive operations to background
    background_tasks.add_task(db_utils.process_tags, link_id, tag_names)
    background_tasks.add_task(db_utils.update_frecency)
    
    return {"id": link_id}
```

**Operations suitable for background processing:**
- Tag processing
- Frecency calculations
- Temporary link cleanup
- Database maintenance tasks

## 9. Optimize Temporary Link Cleanup

The current implementation checks all links during cleanup. Optimize by:

```python
def purge_expired_links_optimized(now: Optional[int] = None) -> int:
    """
    Delete links whose expires_at timestamp is in the past, with optimizations.
    """
    con = _get_connection()
    cur = con.cursor()
    if now is None:
        now = int(time())
    
    # Only query links that have an expiration date and are expired
    cur.execute(
        """
        DELETE FROM links 
        WHERE expires_at IS NOT NULL 
        AND expires_at <= :now
        AND expires_at > :cutoff
        """,
        {"now": now, "cutoff": now - 86400}  # Only check links expired in the last 24 hours
    )
    removed = cur.rowcount or 0
    con.commit()
    con.close()

    # Clean up orphaned tags after deletion
    if removed > 0:
        _cleanup_orphaned_tags()

    return removed
```

**Additional improvements:**
1. Use a scheduled job instead of a continuous loop
2. Implement batch deletion for expired links
3. Add an index on `(expires_at, id)` for faster cleanup operations

## 10. Use Prepared Statements

Ensure all frequently used SQL queries use prepared statements to avoid parsing overhead:

```python
# Create prepared statements once
_get_links_stmt = None

def get_links(page=0, batch=None):
    global _get_links_stmt
    con = _get_connection()
    
    if _get_links_stmt is None:
        _get_links_stmt = con.prepare(
            "SELECT id, url, name, rank, accessed, expires_at FROM links " 
            "ORDER BY ... LIMIT ?, ?"
        )
    
    # Use the prepared statement
    rows = _get_links_stmt.execute((offset, batch))
    # Process results...
```

## Implementation Priority

1. **High Priority (Immediate Impact)**
   - Database indexing
   - Connection pooling
   - Query optimization for frecency calculation

2. **Medium Priority (Significant Improvement)**
   - Implement caching
   - Optimize search functionality
   - Batch processing for tag operations

3. **Lower Priority (Future Scaling)**
   - Pagination optimization
   - Async processing
   - Temporary link cleanup optimization
   - Prepared statements

## Monitoring and Benchmarking

After implementing these changes, it's recommended to:

1. Benchmark before and after each major change
2. Monitor database query performance
3. Track memory usage and connection patterns
4. Measure response times for key endpoints

These metrics will help quantify the impact of the optimizations and identify any remaining bottlenecks.
