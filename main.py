import sqlite3

import uvicorn
from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from packaging.version import parse

import services.db_utils as db_utils
import services.app_config as app_config

# Initialize the database, with the current app version.
db_utils.init_db("1")

config = {}  # Global config dictionary, str: object, or str: str.

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

# set up the templates
templates = Jinja2Templates(directory="templates")


# get first page of links
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, page: int = 0):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "links": lks,
            "page": page,
            "version": config["app_version"],
            "name": config["app_name"],
        },
    )


# Dashboard
@app.get("/dashboard/", response_class=HTMLResponse)
async def dashboard(request: Request, page: int = 0):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "links": lks,
            "page": page
        },
    )


# get next page of links for infinite scroll
@app.get("/links/{page}", response_class=HTMLResponse)
async def links(request: Request, page: int):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "links.html",
        {"request": request, "links": lks, "page": page, "next_page": page + 1},
    )


# get next page of links for infinite scroll
@app.get("/dashboard_items/{page}", response_class=HTMLResponse)
async def links(request: Request, page: int):
    lks = db_utils.get_links(page)
    return templates.TemplateResponse(
        "dashboard_items.html",
        {"request": request, "links": lks, "page": page, "next_page": page + 1},
    )


# search for links:
@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, text: str):
    lks = db_utils.search_links(text)
    return templates.TemplateResponse(
        "links.html", {"request": request, "links": lks, "search_term": text}
    )


# add a new link
@app.get("/add", response_class=HTMLResponse)
async def add_display(request: Request):
    return templates.TemplateResponse("add.html", {"request": request})


# process the new link
@app.post("/add", response_class=HTMLResponse)
async def add_link(link_name: str = Form(...), link_url: str = Form(...)):
    db_utils.save_link(link_name, link_url)
    return RedirectResponse(app.url_path_for("root"), status_code=302)


# Redirect to the url of the link
@app.get("/redirect/{link_id}")
async def redirect(background_tasks: BackgroundTasks, link_id):
    link = db_utils.get_link(link_id)[2]
    background_tasks.add_task(
        db_utils.decrement_rank, 1000
    )  # TODO: Change max_rank to a config value in the database.
    return RedirectResponse(link, status_code=301)


# edit individual link
@app.get("/edit/{link_id}", response_class=HTMLResponse)
async def edit(request: Request, link_id):
    return templates.TemplateResponse(
        "edit.html", {"request": request, "link": db_utils.get_link(link_id)}
    )


# process the edit link form
@app.post("/edit/{link_id}", response_class=HTMLResponse)
async def edit_link(link_id, link_name: str = Form(...), link_url: str = Form(...)):
    db_utils.save_link(link_name, link_url, link_id)
    return RedirectResponse(app.url_path_for("root"), status_code=302)


# delete individual link
@app.get("/delete/{link_id}", response_class=HTMLResponse)
async def delete(link_id):
    db_utils.delete_link(link_id)
    return RedirectResponse("/dashboard/")


# start the server
if __name__ == "__main__":
    uvicorn.run(app, port=8001, host="127.0.0.1")
