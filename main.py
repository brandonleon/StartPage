import sqlite3
from typing import List

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from packaging.version import parse
from starlette.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import services.app_config as ap
import services.db_utils as db_utils

# Initialize the database, with the current app version.
db_utils.init_db("2")

config = {}  # Global config dictionary, str: object, or str: str.
# app_config = ap.AppConfig("1.0.0", db)

# Read config values from the database, if they exist.
# else set version to 0.0
try:
    config = db_utils.read_config()
    config["db_version"] = parse(config["db_version"])
except sqlite3.OperationalError:
    config["db_version"] = parse("0.0")

config["app_version"] = parse(db_utils.get_app_metadata()["version"])
config["app_name"] = db_utils.get_app_metadata()["name"]

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

def template_context(**extra):
    ctx = {
        "version": str(config["app_version"]),
        "name": config["app_name"],
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
    return templates.TemplateResponse(
        "add.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Add Link",
            all_tags=all_tags,
        ),
    )


# process the new link
@app.post("/add", response_class=HTMLResponse)
async def add_link(
    link_name: str = Form(...),
    link_url: str = Form(...),
    tag_names: str = Form(""),
):
    # Save the link and get the link_id
    link_id = db_utils.save_link(link_name, link_url)

    # Process tags if provided
    if tag_names.strip():
        # Split by comma and process each tag
        tags = [tag.strip() for tag in tag_names.split(",") if tag.strip()]
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
    return templates.TemplateResponse(
        "edit.html",
        template_context(
            request=request,
            link=link,
            tags=tags,
            all_tags=all_tags,
            title=f"{config['app_name']} · Edit Link",
        ),
    )


# process the edit link form
@app.post("/edit/{link_id}", response_class=HTMLResponse)
async def edit_link(link_id, link_name: str = Form(...), link_url: str = Form(...)):
    db_utils.save_link(link_name, link_url, link_id)
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
    frecency = db_utils.get_frecency_config()
    counts = db_utils.get_count()
    saved = request.query_params.get("saved") == "1"
    return templates.TemplateResponse(
        "settings.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Settings",
            frecency=frecency,
            counts=counts,
            form_values=frecency,
            errors={},
            saved=saved,
        ),
    )


@app.post("/settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    batch_size: int = Form(...),
    max_rank: int = Form(...),
):
    errors = {}
    if batch_size < 5 or batch_size > 200:
        errors["batch_size"] = "Choose a batch size between 5 and 200."
    if max_rank < 100 or max_rank > 50000:
        errors["max_rank"] = "Choose a max rank between 100 and 50000."

    if errors:
        counts = db_utils.get_count()
        frecency = db_utils.get_frecency_config()
        return templates.TemplateResponse(
            "settings.html",
            template_context(
                request=request,
                title=f"{config['app_name']} · Settings",
                frecency=frecency,
                counts=counts,
                form_values={"batch_size": batch_size, "max_rank": max_rank},
                errors=errors,
                saved=False,
            ),
            status_code=400,
        )

    db_utils.update_frecency_config(batch_size, max_rank)
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


# start the server
if __name__ == "__main__":
    uvicorn.run(app, port=8001, host="127.0.0.1")
