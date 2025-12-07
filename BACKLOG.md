# Backlog

## Bulk export & backup flow
- **Problem**: Power users currently need to poke `data/links.db` manually (or hack `services/io_utils.py`) to snapshot their collection, which is risky and unfriendly.
- **Proposal**: Build on the existing `export_db_links` helper to stream a CSV/JSON export via a `/export` route and surface it from the dashboard/help page. Persist exports to a temp file for download rather than printing to stdout.
- **Notes**: Include link metadata (id, name, url, rank, accessed) plus associated tags so the export can be re-imported later. Document the workflow in README/help.

## Surface frecency tuning in the UI
- **Problem**: Key frecency parameters (batch size per page and `max_rank` prune threshold) live hardcoded in `db_utils.py`, so operators must edit code/DB rows to adjust how aggressive cleanup is.
- **Proposal**: Add a lightweight settings view that reads/writes these values to the `config` table and expose it in the navbar. The dashboard can reflect the live config (e.g., show pages × batch size).
- **Notes**: Validate inputs server-side, update `get_count`/`get_stats` to respect new config, and flag when changes require a restart.
