from playwright.sync_api import Page


# test Startpage
def test_main(page: Page):
    page.goto("http://127.0.0.1:8000/")
    assert page.title() == "StartPage - Links"


# test dashboard
def test_dashboard(page: Page):
    page.goto("http://127.0.0.1:8000/dashboard")
    assert page.title() == "StartPage - Dashboard"


# test add link
def test_add_link(page: Page):
    page.goto("http://127.0.0.1:8000/add")
    assert page.title() == "StartPage - Add new link"
