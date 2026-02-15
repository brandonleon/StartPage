import os
from pathlib import Path

TEST_CONFIG_PATH = Path(__file__).resolve().parent / "test_config.toml"
os.environ["STARTPAGE_CONFIG_PATH"] = str(TEST_CONFIG_PATH)

import services.config_cli as config_cli  # noqa: E402
import services.db_utils as db_utils  # noqa: E402
from services import app_config  # noqa: E402


def setup_module(module):
    if TEST_CONFIG_PATH.exists():
        TEST_CONFIG_PATH.unlink()
    app_config.reload_runtime_config()


def teardown_module(module):
    if TEST_CONFIG_PATH.exists():
        TEST_CONFIG_PATH.unlink()
    app_config.reload_runtime_config()


def test_trusted_proxies_set_and_show(capsys):
    original = db_utils.get_trusted_proxy_cidrs()
    try:
        rc = config_cli.main(["trusted-proxies", "set", "172.17.0.1", "172.17.0.0/16"])
        assert rc == 0
        assert capsys.readouterr().out.splitlines() == ["172.17.0.1/32", "172.17.0.0/16"]

        rc = config_cli.main(["trusted-proxies", "show"])
        assert rc == 0
        assert capsys.readouterr().out.splitlines() == ["172.17.0.1/32", "172.17.0.0/16"]
    finally:
        db_utils.update_trusted_proxy_cidrs(original)


def test_trusted_proxies_add_and_remove(capsys):
    original = db_utils.get_trusted_proxy_cidrs()
    try:
        rc = config_cli.main(["trusted-proxies", "set", "127.0.0.1/32"])
        assert rc == 0
        capsys.readouterr()

        rc = config_cli.main(["trusted-proxies", "add", "172.17.0.1", "172.17.0.1/32"])
        assert rc == 0
        assert capsys.readouterr().out.splitlines() == ["127.0.0.1/32", "172.17.0.1/32"]

        rc = config_cli.main(["trusted-proxies", "remove", "172.17.0.1"])
        assert rc == 0
        assert capsys.readouterr().out.splitlines() == ["127.0.0.1/32"]
    finally:
        db_utils.update_trusted_proxy_cidrs(original)
