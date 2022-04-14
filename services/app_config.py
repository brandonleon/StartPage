from packaging.version import parse


class Config:
    """
    Class for keeping track of the application configuration.
    """

    def __init__(self, app_version: str = '1.0.0', db_version: str = '1.0.0', batch=20):
        """
        Initialize the configuration.
        """
        self.app_version = parse(app_version)
        self.db_version = parse(db_version)