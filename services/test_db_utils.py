import sqlite3

import services.db_utils as db_utils


# Ensure count and pages are integers
def test_get_count():
    assert isinstance(db_utils.get_count()["count"], int)
    assert isinstance(db_utils.get_count()["pages"], int)


# Ensure a list of links is returned
def test_get_links():
    # Ensure a list is returned.
    assert isinstance(db_utils.get_links(), list)
    # Ensure the list contains links by validate the first link.
    assert isinstance(db_utils.get_links()[0]["id"], str)
    assert isinstance(db_utils.get_links()[0]["url"], str)
    assert isinstance(db_utils.get_links()[0]["name"], str)
    assert isinstance(db_utils.get_links()[0]["rank"], float)
    assert isinstance(db_utils.get_links()[0]["accessed"], str)
