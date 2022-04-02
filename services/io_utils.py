import csv
import services.db_utils as db_utils


# export database links to csv file
def export_db_links():
    links = db_utils.get_links(0, 20000)
    for link in links:
       print(link)
