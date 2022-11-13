from packaging.version import parse
from packaging.version import Version


class AppConfig:
    """
    Class for keeping track of the application configuration.
    """

    def __init__(self, app_version: str, db_version: Version):
        """
        Initialize the configuration.
        """
        self.app_version = parse(app_version)
        self.db_version = db_version
