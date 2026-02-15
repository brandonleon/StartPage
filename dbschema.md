# StartPage Database Schema

The application uses SQLite with the following tables:

``` mermaid
erDiagram
    links }o--o{ tagmap : tags
    tagmap }o--o{ tags : tags
    metadata

    links {
        varchar id
        text name
        text url
        float rank
        accessed datetime
        expires_at datetime
    }

    metadata {
        text name
        text value
    }

    tagmap {
        int linkid
        int tagid
    }

    tags {
        int id
        text name
    }
```

## Table Descriptions

### links
Stores all bookmarked links with frecency-based ranking.

- `id` (VARCHAR): UUID primary key
- `name` (TEXT): Unique display name for the link
- `url` (TEXT): Unique URL
- `rank` (FLOAT): Frecency score (incremented on each access)
- `accessed` (INTEGER): Unix timestamp of last access
- `expires_at` (INTEGER, nullable): Unix timestamp when the link should be automatically deleted

### tags
Stores unique tag names.

- `id` (INTEGER): Auto-incrementing primary key
- `name` (TEXT): Unique lowercase tag name

### tagmap
Junction table for many-to-many relationship between links and tags.

- `linkid` (VARCHAR): Foreign key to links.id
- `tagid` (INTEGER): Foreign key to tags.id

**Usage**: Tags allow organizing links into categories. Multiple tags can be assigned to a single link, and each tag can be applied to multiple links. Tags are automatically lowercased, whitespace is replaced with hyphens, non-alphanumeric characters are removed, and duplicates are deduped.

### metadata
Schema version tracking and database-backed operational settings.

- `name` (TEXT): Metadata key (e.g., 'db_version')
- `value` (TEXT): Metadata value
- `metrics_whitelist` uses comma-separated IP/CIDR values that gate access to `GET /metrics`

## Schema Versioning

Current version: **v2**

Schema migrations are managed through:
- `sql_scripts/db_v1.sql` - Full schema definition
- `sql_scripts/v{old}_to_{new}.sql` - Migration scripts

Version is checked on startup and migrations run automatically if needed.

## Runtime Configuration

Application settings (batch size, pruning thresholds, and temporary-link options) now live in `config.toml` at the project root. Deployments can override this path with the `STARTPAGE_CONFIG_PATH` environment variable. The FastAPI app loads the TOML file on boot, keeps the values in memory, and persists edits from the `/settings` screen back to disk so they apply immediately without touching SQLite.
