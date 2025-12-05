import sqlite3

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
db_utils.init_db("1")

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
    return templates.TemplateResponse(
        "index.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            title=f"{config['app_name']} · Home",
        ),
    )


# Dashboard
@app.get("/dashboard/", response_class=HTMLResponse)
async def dashboard(request: Request, page: int = 0):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "dashboard.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            title=f"{config['app_name']} · Dashboard",
        ),
    )


# get next page of links for infinite scroll
@app.get("/links/{page}", response_class=HTMLResponse)
async def links(request: Request, page: int):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "links.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            next_page=page + 1,
        ),
    )


# get next page of links for infinite scroll
@app.get("/dashboard_items/{page}", response_class=HTMLResponse)
async def links(request: Request, page: int):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "dashboard_items.html",
        template_context(
            request=request,
            links=lks,
            page=page,
            next_page=page + 1,
        ),
    )


# search for links:
@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, text: str = ""):
    query = text.strip()
    if not query:
        lks = db_utils.get_links(0)
        next_page = 1 if len(lks) == 20 else None
    else:
        lks = db_utils.search_links(query)
        next_page = None

    return templates.TemplateResponse(
        "links.html",
        template_context(
            request=request,
            links=lks,
            search_term=query,
            next_page=next_page,
        ),
    )


# add a new link
@app.get("/add", response_class=HTMLResponse)
async def add_display(request: Request):
    return templates.TemplateResponse(
        "add.html",
        template_context(
            request=request,
            title=f"{config['app_name']} · Add Link",
        ),
    )


# process the new link
@app.post("/add", response_class=HTMLResponse)
async def add_link(link_name: str = Form(...), link_url: str = Form(...)):
    db_utils.save_link(link_name, link_url)
    return RedirectResponse(app.url_path_for("root"), status_code=302)


# Redirect to the url of the link
@app.get("/redirect/{link_id}")
async def redirect(background_tasks: BackgroundTasks, link_id):
    link = db_utils.get_link(link_id, True)[2]
    background_tasks.add_task(
        db_utils.decrement_rank, 1000
    )  # TODO: Change max_rank to a config value in the database.
    return RedirectResponse(link, status_code=302)


# edit individual link
@app.get("/edit/{link_id}", response_class=HTMLResponse)
async def edit(request: Request, link_id):
    return templates.TemplateResponse(
        "edit.html",
        template_context(
            request=request,
            link=db_utils.get_link(link_id, False),
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


# start the server
if __name__ == "__main__":
    uvicorn.run(app, port=8001, host="127.0.0.1")
