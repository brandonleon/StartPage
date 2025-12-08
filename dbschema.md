# StartPage Database Schema

The application uses SQLite with the following tables:

``` mermaid
erDiagram
    links }o--o{ tagmap : tags
    tagmap }o--o{ tags : tags
    config
    metadata

    links {
        varchar id
        text name
        text url
        float rank
        accessed datetime
        expires_at datetime
    }

    config {
        text name
        text value
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

### config
Application configuration settings.

- `name` (TEXT): Setting name (e.g., 'batch' or 'max_rank')
- `value` (TEXT): Setting value

Current keys:

- `batch`: Links per page batch size shown on dashboards and the home feed
- `max_rank`: Maximum rank pool allowed before the pruning job runs
- `temp_links_enabled`: Whether temporary link inputs/cleanup are active
- `temp_links_default_ttl_hours`: Default duration (hours) applied when users choose the "Default" preset
- `temp_links_max_custom_hours`: Maximum hours permitted for custom durations (capped at 30 days)
- `temp_links_purge_interval_seconds`: Background cleanup cadence for purging expired links

### metadata
Schema version tracking for migrations.

- `name` (TEXT): Metadata key (e.g., 'db_version')
- `value` (TEXT): Metadata value

## Schema Versioning

Current version: **v2**

Schema migrations are managed through:
- `sql_scripts/db_v1.sql` - Full schema definition
- `sql_scripts/v{old}_to_{new}.sql` - Migration scripts

Version is checked on startup and migrations run automatically if needed.
