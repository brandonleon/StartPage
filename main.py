import asyncio
import contextlib
import sqlite3
from math import ceil
from time import time
from typing import Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from packaging.version import parse
from starlette.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import services.db_utils as db_utils

# Initialize the database, with the current app version.
db_utils.init_db("2")
temp_link_settings = db_utils.get_temp_link_config()


def _refresh_temp_link_settings() -> None:
    global temp_link_settings
    temp_link_settings = db_utils.get_temp_link_config()

config: Dict[str, object] = {}
try:
    metadata = db_utils.read_metadata()
    db_version_raw = metadata.get("db_version", "0.0")
except sqlite3.OperationalError:
    db_version_raw = "0.0"
config["db_version"] = parse(str(db_version_raw))

app_metadata = db_utils.get_app_metadata()
config["app_version"] = parse(app_metadata["version"])
config["app_name"] = app_metadata["name"]

if config["app_version"].major != config["db_version"].major:
    db_utils.upgrade_db(config["db_version"].major, config["app_version"].major)

# Create the app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# set up the templates
templates = Jinja2Templates(directory="templates")

SEARCH_PARTIALS = {
    "links": "links.html",
    "dashboard": "dashboard_items.html",
}


TEMP_LINK_PRESETS: Dict[str, Optional[int]] = {
    "default": None,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}


def _temp_link_preset_options() -> List[Dict[str, str]]:
    return [
        {
            "value": "default",
            "label": f"Default ({temp_link_settings['default_ttl_hours']} hours)",
        },
        {"value": "24h", "label": "24 hours"},
        {"value": "7d", "label": "7 days"},
        {"value": "custom", "label": "Custom"},
    ]


def _hours_remaining(expires_at: Optional[int]) -> Optional[int]:
    if not expires_at:
        return None
    seconds = max(0, expires_at - int(time()))
    return max(1, ceil(seconds / 3600))


def _custom_duration_seconds(raw_hours: Optional[str], max_hours: int) -> Optional[int]:
    if raw_hours is None:
        return None
    try:
        hours = float(raw_hours)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    hours = min(max(hours, 1.0), float(max_hours))
    return int(ceil(hours * 3600))


def _resolve_expiration(
    temporary_flag: Optional[str],
    preset: Optional[str],
    custom_hours: Optional[str],
) -> Optional[int]:
    if not temp_link_settings["enabled"] or not temporary_flag:
        return None
    preset_key = (preset or "default").lower()
    if preset_key == "default":
        ttl_seconds = temp_link_settings["default_ttl_hours"] * 3600
    elif preset_key in {"24h", "7d"}:
        ttl_seconds = TEMP_LINK_PRESETS[preset_key]
    elif preset_key == "custom":
        ttl_seconds = _custom_duration_seconds(
            custom_hours, temp_link_settings["max_custom_hours"]
        ) or (temp_link_settings["default_ttl_hours"] * 3600)
    else:
        ttl_seconds = temp_link_settings["default_ttl_hours"] * 3600
    return int(time()) + ttl_seconds


def _build_temp_link_form(
    enabled: bool = False,
    preset: Optional[str] = None,
    custom_hours: Optional[int] = None,
    default_hours: Optional[int] = None,
) -> Dict[str, Optional[int]]:
    default_hours = default_hours or temp_link_settings["default_ttl_hours"]
    preset_key = (preset or "default").lower()
    if preset_key not in {"default", "24h", "7d", "custom"}:
        preset_key = "default"
    effective_enabled = enabled and temp_link_settings["enabled"]
    show_custom = effective_enabled and preset_key == "custom"
    if preset_key == "custom" and custom_hours is None:
        custom_hours = default_hours
    return {
        "enabled": effective_enabled,
        "preset": preset_key,
        "custom_hours": custom_hours if show_custom else None,
        "show_custom": show_custom,
    }

def template_context(**extra):
    ctx = {
        "version": str(config["app_version"]),
        "name": config["app_name"],
        "temp_links_enabled": temp_link_settings["enabled"],
        "temp_link_default_hours": temp_link_settings["default_ttl_hours"],
        "temp_link_max_custom_hours": temp_link_settings["max_custom_hours"],
        "temp_link_presets": _temp_link_preset_options(),
        "temp_link_purge_interval_minutes": temp_link_settings["purge_interval_seconds"]
        // 60,
    }
    ctx.update(extra)
    return ctx


# Serve favicon
@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")


# get first page of links
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, page: int = 0):
    lks = db_utils.get_links(page)
    tags = db_utils.get_all_tags()
    frecency = db_utils.get_frecency_config()
    return templates.TemplateResponse(
        "index.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            title=f"{config['app_name']} · Home",
            all_tags=tags,
            batch_size=frecency["batch_size"],
        ),
    )


# Dashboard
@app.get("/dashboard/", response_class=HTMLResponse)
async def dashboard(request: Request, page: int = 0):
    lks = db_utils.get_links(page)
    tags = db_utils.get_all_tags()
    counts = db_utils.get_count()
    frecency = db_utils.get_frecency_config()
    return templates.TemplateResponse(
        "dashboard.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            title=f"{config['app_name']} · Dashboard",
            all_tags=tags,
            counts=counts,
            frecency=frecency,
        ),
    )


# get next page of links for infinite scroll
@app.get("/links/{page}", response_class=HTMLResponse)
async def links(request: Request, page: int):
    lks = db_utils.get_links(page)
    frecency = db_utils.get_frecency_config()
    next_page = page + 1 if len(lks) == frecency["batch_size"] else None
    return templates.TemplateResponse(
        "links.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            next_page=next_page,
            batch_size=frecency["batch_size"],
        ),
    )


# get next page of links for infinite scroll
@app.get("/dashboard_items/{page}", response_class=HTMLResponse)
async def links(request: Request, page: int):
    lks = db_utils.get_links(page)
    frecency = db_utils.get_frecency_config()
    next_page = page + 1 if len(lks) == frecency["batch_size"] else None
    return templates.TemplateResponse(
        "dashboard_items.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            next_page=next_page,
        ),
    )


# search for links:
@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, text: str = "", view: str = "links"):
    query = text.strip()
    frecency = db_utils.get_frecency_config()
    if not query:
        lks = db_utils.get_links(0)
        next_page = 1 if len(lks) == frecency["batch_size"] else None
    else:
        lks = db_utils.search_links(query)
        next_page = None

    template_name = SEARCH_PARTIALS.get(view, SEARCH_PARTIALS["links"])

    return templates.TemplateResponse(
        template_name,
        template_context(
            request=request,
            links=lks,
            search_term=query,
            next_page=next_page,
            batch_size=frecency["batch_size"],
        ),
    )


# add a new link
@app.get("/add", response_class=HTMLResponse)
async def add_display(request: Request):
    all_tags = db_utils.get_all_tags()
    default_values = {
        "link_name": "",
        "link_url": "",
        "tag_names": "",
        "is_temporary": False,
        "temporary_preset": "default",
        "temporary_custom_hours": "",
    }
    return templates.TemplateResponse(
        "add.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Add Link",
            all_tags=all_tags,
            temp_link_form=_build_temp_link_form(
                enabled=False,
                preset="default",
                default_hours=temp_link_settings["default_ttl_hours"],
            ),
            form_values=default_values,
            errors={},
        ),
    )


@app.get("/duplicates/check", response_class=HTMLResponse)
async def check_duplicate_link(
    request: Request,
    field: str,
    link_name: Optional[str] = None,
    link_url: Optional[str] = None,
):
    lookup_field = field.strip().lower()
    if lookup_field == "name":
        value = (link_name or "").strip()
        finder = db_utils.find_link_by_name
    elif lookup_field == "url":
        value = (link_url or "").strip()
        finder = db_utils.find_link_by_url
    else:
        raise HTTPException(status_code=400, detail="Invalid field")

    if not value:
        return HTMLResponse("")

    duplicate = finder(value)
    if not duplicate:
        return HTMLResponse("")

    return templates.TemplateResponse(
        "partials/duplicate_link_warning.html",
        {
            "request": request,
            "duplicate": duplicate,
            "duplicate_field": lookup_field,
            "duplicate_value": value,
        },
    )


# process the new link
@app.post("/add", response_class=HTMLResponse)
async def add_link(
    request: Request,
    link_name: str = Form(...),
    link_url: str = Form(...),
    tag_names: str = Form(""),
    is_temporary: Optional[str] = Form(None),
    temporary_preset: str = Form("24h"),
    temporary_custom_hours: Optional[str] = Form(None),
):
    form_values = {
        "link_name": link_name.strip(),
        "link_url": link_url.strip(),
        "tag_names": tag_names.strip(),
        "is_temporary": is_temporary is not None,
        "temporary_preset": temporary_preset,
        "temporary_custom_hours": (temporary_custom_hours or "").strip(),
    }
    # Save the link and get the link_id
    expires_at = _resolve_expiration(
        is_temporary, temporary_preset, temporary_custom_hours
    )
    try:
        link_id = db_utils.save_link(form_values["link_name"], form_values["link_url"], expires_at=expires_at)
    except db_utils.DuplicateLinkError as exc:
        field_key = "link_name" if exc.field == "name" else "link_url"
        errors = {
            field_key: f"A link with this {exc.field} already exists. Use the existing entry instead."
        }
        all_tags = db_utils.get_all_tags()
        temp_form = _build_temp_link_form(
            enabled=form_values["is_temporary"],
            preset=form_values["temporary_preset"],
            custom_hours=int(form_values["temporary_custom_hours"]) if form_values["temporary_custom_hours"] else None,
        )
        return templates.TemplateResponse(
            "add.html",
            template_context(
                request=request,
                title=f"{config['app_name']} · Add Link",
                all_tags=all_tags,
                temp_link_form=temp_form,
                form_values=form_values,
                errors=errors,
            ),
            status_code=400,
        )

    # Process tags if provided
    if form_values["tag_names"]:
        # Split by comma and process each tag
        tags = [tag.strip() for tag in form_values["tag_names"].split(",") if tag.strip()]
        for tag in tags:
            db_utils.add_tag_to_link(link_id, tag)

    return RedirectResponse(app.url_path_for("root"), status_code=302)


# Redirect to the url of the link
@app.get("/redirect/{link_id}")
async def redirect(background_tasks: BackgroundTasks, link_id):
    link = db_utils.get_link(link_id, True)[2]
    background_tasks.add_task(db_utils.decrement_rank)
    return RedirectResponse(link, status_code=302)


# edit individual link
@app.get("/edit/{link_id}", response_class=HTMLResponse)
async def edit(request: Request, link_id):
    link = db_utils.get_link(link_id, False)
    tags = db_utils.get_tags_for_link(link_id)
    all_tags = db_utils.get_all_tags()
    expires_at = link["expires_at"] if link else None
    expires_hours = _hours_remaining(expires_at)
    preset = "custom" if expires_at else "default"
    temp_link_form = _build_temp_link_form(
        enabled=bool(expires_at),
        preset=preset,
        custom_hours=expires_hours,
    )
    temp_link_summary = db_utils.format_expires_in(expires_at) if expires_at else None
    return templates.TemplateResponse(
        "edit.html",
        template_context(
            request=request,
            link=link,
            tags=tags,
            all_tags=all_tags,
            title=f"{config['app_name']} · Edit Link",
            temp_link_form=temp_link_form,
            temp_link_summary=temp_link_summary,
        ),
    )


# process the edit link form
@app.post("/edit/{link_id}", response_class=HTMLResponse)
async def edit_link(
    link_id,
    link_name: str = Form(...),
    link_url: str = Form(...),
    is_temporary: Optional[str] = Form(None),
    temporary_preset: str = Form("24h"),
    temporary_custom_hours: Optional[str] = Form(None),
):
    expires_at = _resolve_expiration(
        is_temporary, temporary_preset, temporary_custom_hours
    )
    db_utils.save_link(link_name, link_url, link_id, expires_at)
    return RedirectResponse(app.url_path_for("root"), status_code=302)


# delete individual link
@app.delete("/delete/{link_id}", response_class=HTMLResponse)
async def delete(request: Request, link_id):
    db_utils.delete_link(link_id)
    print(link_id)
    return templates.TemplateResponse(
        "delete.html",
        template_context(request=request),
    )


@app.post("/dashboard/bulk-delete")
async def bulk_delete(selected_links: List[str] = Form(default=[])):
    if selected_links:
        for link_id in selected_links:
            db_utils.delete_link(link_id)
    return RedirectResponse(app.url_path_for("dashboard"), status_code=303)


@app.post("/dashboard/bulk-tag")
async def bulk_tag(selected_links: List[str] = Form(default=[]), tag_names: str = Form(...)):
    tags = [tag.strip() for tag in tag_names.split(",") if tag.strip()]
    if not selected_links or not tags:
        return RedirectResponse(app.url_path_for("dashboard"), status_code=303)

    for link_id in selected_links:
        for tag in tags:
            db_utils.add_tag_to_link(link_id, tag)
    return RedirectResponse(app.url_path_for("dashboard"), status_code=303)


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse(
        "help.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Help",
            db_path=db_utils.db_path,
        ),
    )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    stats = db_utils.get_stats()
    return templates.TemplateResponse(
        "stats.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Statistics",
            stats=stats,
        ),
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    _refresh_temp_link_settings()
    frecency = db_utils.get_frecency_config()
    saved = request.query_params.get("saved") == "1"
    temp_config = temp_link_settings
    form_values = {
        "batch_size": frecency["batch_size"],
        "max_rank": frecency["max_rank"],
        "temp_links_enabled": temp_config["enabled"],
        "temp_link_default_ttl_hours": temp_config["default_ttl_hours"],
        "temp_link_max_custom_hours": temp_config["max_custom_hours"],
        "temp_link_purge_interval_minutes": temp_config["purge_interval_seconds"] // 60,
    }
    return templates.TemplateResponse(
        "settings.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Settings",
            frecency=frecency,
            form_values=form_values,
            errors={},
            saved=saved,
        ),
    )


@app.post("/settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    batch_size: int = Form(...),
    max_rank: int = Form(...),
    temp_links_enabled: Optional[str] = Form(None),
    temp_link_default_ttl_hours: int = Form(...),
    temp_link_max_custom_hours: int = Form(...),
    temp_link_purge_interval_minutes: int = Form(...),
):
    errors = {}
    if batch_size < 5 or batch_size > 200:
        errors["batch_size"] = "Choose a batch size between 5 and 200."
    if max_rank < 100 or max_rank > 50000:
        errors["max_rank"] = "Choose a max rank between 100 and 50000."
    if temp_link_default_ttl_hours < 1 or temp_link_default_ttl_hours > 720:
        errors["temp_link_default_ttl_hours"] = "Pick a default duration between 1 and 720 hours."
    if temp_link_max_custom_hours < temp_link_default_ttl_hours or temp_link_max_custom_hours > 720:
        errors["temp_link_max_custom_hours"] = "Max custom duration must be at least the default and no more than 720 hours."
    if temp_link_purge_interval_minutes < 1 or temp_link_purge_interval_minutes > 1440:
        errors["temp_link_purge_interval_minutes"] = "Cleanup interval must be between 1 minute and 24 hours."

    if errors:
        frecency = db_utils.get_frecency_config()
        form_values = {
            "batch_size": batch_size,
            "max_rank": max_rank,
            "temp_links_enabled": temp_links_enabled is not None,
            "temp_link_default_ttl_hours": temp_link_default_ttl_hours,
            "temp_link_max_custom_hours": temp_link_max_custom_hours,
            "temp_link_purge_interval_minutes": temp_link_purge_interval_minutes,
        }
        return templates.TemplateResponse(
            "settings.html",
            template_context(
                request=request,
                title=f"{config['app_name']} · Settings",
                frecency=frecency,
                form_values=form_values,
                errors=errors,
                saved=False,
            ),
            status_code=400,
        )

    db_utils.update_frecency_config(batch_size, max_rank)
    db_utils.update_temp_link_config(
        temp_links_enabled is not None,
        temp_link_default_ttl_hours,
        temp_link_max_custom_hours,
        temp_link_purge_interval_minutes * 60,
    )
    _refresh_temp_link_settings()
    return RedirectResponse(app.url_path_for("settings_page") + "?saved=1", status_code=303)


# Tag management routes
@app.get("/tags", response_class=HTMLResponse)
async def tags_page(request: Request):
    tags = db_utils.get_all_tags()
    return templates.TemplateResponse(
        "tags.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Tags",
            tags=tags,
        ),
    )


@app.post("/link/{link_id}/tag", response_class=HTMLResponse)
async def add_tag(link_id: str, tag_name: str = Form(...)):
    # Parse comma-separated tags
    if tag_name.strip():
        tags = [tag.strip() for tag in tag_name.split(",") if tag.strip()]
        for tag in tags:
            db_utils.add_tag_to_link(link_id, tag)
    return RedirectResponse(app.url_path_for("root"), status_code=302)


@app.delete("/link/{link_id}/tag/{tag_id}", response_class=HTMLResponse)
async def remove_tag(request: Request, link_id: str, tag_id: str):
    db_utils.remove_tag_from_link(link_id, tag_id)
    return templates.TemplateResponse(
        "tag_removed.html",
        template_context(request=request),
    )


@app.delete("/tag/{tag_id}", response_class=HTMLResponse)
async def delete_tag_route(request: Request, tag_id: str):
    db_utils.delete_tag(tag_id)
    return templates.TemplateResponse(
        "tag_deleted.html",
        template_context(request=request),
    )


@app.post("/tag/{tag_id}/rename")
async def rename_tag_route(tag_id: str, new_name: str = Form(...)):
    db_utils.rename_tag(tag_id, new_name)
    return RedirectResponse(app.url_path_for("tags_page"), status_code=303)


@app.get("/tag/{tag_name}", response_class=HTMLResponse)
async def filter_by_tag(request: Request, tag_name: str, page: int = 0):
    lks = db_utils.get_links_by_tag(tag_name, page)
    tags = db_utils.get_all_tags()
    frecency = db_utils.get_frecency_config()
    return templates.TemplateResponse(
        "index.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            title=f"{config['app_name']} · Tag: {tag_name}",
            filtered_tag=tag_name,
            all_tags=tags,
            batch_size=frecency["batch_size"],
        ),
    )


@app.get("/tag/{tag_name}/links/{page}", response_class=HTMLResponse)
async def tag_links_page(request: Request, tag_name: str, page: int):
    lks = db_utils.get_links_by_tag(tag_name, page)
    frecency = db_utils.get_frecency_config()
    next_page = page + 1 if len(lks) == frecency["batch_size"] else None
    return templates.TemplateResponse(
        "links.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            next_page=next_page,
            filtered_tag=tag_name,
            batch_size=frecency["batch_size"],
        ),
    )


async def _temp_link_cleanup_loop() -> None:
    while True:
        db_utils.purge_expired_links()
        await asyncio.sleep(temp_link_settings["purge_interval_seconds"])


@app.on_event("startup")
async def _start_temp_link_cleanup() -> None:
    db_utils.purge_expired_links()
    app.state.temp_link_cleanup = asyncio.create_task(_temp_link_cleanup_loop())


@app.on_event("shutdown")
async def _stop_temp_link_cleanup() -> None:
    cleanup_task = getattr(app.state, "temp_link_cleanup", None)
    if cleanup_task:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task


# start the server
if __name__ == "__main__":
    uvicorn.run(app, port=8001, host="127.0.0.1")
