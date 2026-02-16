import argparse
from typing import Optional, Sequence

import services.db_utils as db_utils


def _print_entries(entries: list[str]) -> None:
    if not entries:
        print("(empty)")
        return
    for entry in entries:
        print(entry)


def _cmd_show(_: argparse.Namespace) -> int:
    _print_entries(db_utils.get_metrics_whitelist())
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    _print_entries(db_utils.update_metrics_whitelist(args.entries))
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    _print_entries(db_utils.add_metrics_whitelist_entries(args.entries))
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    _print_entries(db_utils.remove_metrics_whitelist_entries(args.entries))
    return 0


def _cmd_reset(_: argparse.Namespace) -> int:
    _print_entries(db_utils.reset_metrics_whitelist())
    return 0


def _cmd_clear(_: argparse.Namespace) -> int:
    _print_entries(db_utils.update_metrics_whitelist([]))
    return 0


def _cmd_proxies_show(_: argparse.Namespace) -> int:
    _print_entries(db_utils.get_trusted_proxy_cidrs())
    return 0


def _cmd_proxies_set(args: argparse.Namespace) -> int:
    _print_entries(db_utils.update_trusted_proxy_cidrs(args.entries))
    return 0


def _cmd_proxies_add(args: argparse.Namespace) -> int:
    existing = db_utils.get_trusted_proxy_cidrs()
    combined = db_utils.normalize_trusted_proxy_cidrs(existing + args.entries)
    _print_entries(db_utils.update_trusted_proxy_cidrs(combined))
    return 0


def _cmd_proxies_remove(args: argparse.Namespace) -> int:
    existing = db_utils.get_trusted_proxy_cidrs()
    removals = set(db_utils.normalize_trusted_proxy_cidrs(args.entries))
    kept = [entry for entry in existing if entry not in removals]
    _print_entries(db_utils.update_trusted_proxy_cidrs(kept))
    return 0


def _cmd_proxies_reset(_: argparse.Namespace) -> int:
    _print_entries(db_utils.update_trusted_proxy_cidrs(["127.0.0.1/32", "::1/128"]))
    return 0


def _cmd_proxies_clear(_: argparse.Namespace) -> int:
    _print_entries(db_utils.update_trusted_proxy_cidrs([]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage StartPage runtime configuration for /metrics access control."
    )
    config_group = parser.add_subparsers(dest="scope", required=True)
    metrics = config_group.add_parser(
        "metrics-whitelist",
        help="Manage IP/CIDR allow-list for the /metrics endpoint.",
    )
    actions = metrics.add_subparsers(dest="action", required=True)

    show = actions.add_parser("show", help="Show configured whitelist entries.")
    show.set_defaults(handler=_cmd_show)

    set_cmd = actions.add_parser(
        "set",
        help="Replace whitelist entries with one or more IP/CIDR values.",
    )
    set_cmd.add_argument("entries", nargs="+", help="Entries like 127.0.0.1 or 10.0.0.0/8")
    set_cmd.set_defaults(handler=_cmd_set)

    add_cmd = actions.add_parser(
        "add",
        help="Append one or more IP/CIDR values without replacing existing entries.",
    )
    add_cmd.add_argument("entries", nargs="+", help="Entries like 127.0.0.1 or 10.0.0.0/8")
    add_cmd.set_defaults(handler=_cmd_add)

    remove_cmd = actions.add_parser(
        "remove",
        help="Remove one or more IP/CIDR values from the current whitelist.",
    )
    remove_cmd.add_argument("entries", nargs="+", help="Entries like 127.0.0.1 or 10.0.0.0/8")
    remove_cmd.set_defaults(handler=_cmd_remove)

    reset = actions.add_parser(
        "reset", help="Reset whitelist back to local-only defaults (127.0.0.1 and ::1)."
    )
    reset.set_defaults(handler=_cmd_reset)

    clear = actions.add_parser("clear", help="Clear whitelist entries (blocks all clients).")
    clear.set_defaults(handler=_cmd_clear)

    trusted_proxies = config_group.add_parser(
        "trusted-proxies",
        help="Manage trusted proxy IP/CIDR entries used for /metrics forwarded headers.",
    )
    proxy_actions = trusted_proxies.add_subparsers(dest="action", required=True)

    proxies_show = proxy_actions.add_parser("show", help="Show configured trusted proxy entries.")
    proxies_show.set_defaults(handler=_cmd_proxies_show)

    proxies_set = proxy_actions.add_parser(
        "set",
        help="Replace trusted proxy entries with one or more IP/CIDR values.",
    )
    proxies_set.add_argument("entries", nargs="+", help="Entries like 172.17.0.1 or 172.17.0.0/16")
    proxies_set.set_defaults(handler=_cmd_proxies_set)

    proxies_add = proxy_actions.add_parser(
        "add",
        help="Append one or more trusted proxy IP/CIDR values.",
    )
    proxies_add.add_argument("entries", nargs="+", help="Entries like 172.17.0.1 or 172.17.0.0/16")
    proxies_add.set_defaults(handler=_cmd_proxies_add)

    proxies_remove = proxy_actions.add_parser(
        "remove",
        help="Remove one or more trusted proxy IP/CIDR values.",
    )
    proxies_remove.add_argument("entries", nargs="+", help="Entries like 172.17.0.1 or 172.17.0.0/16")
    proxies_remove.set_defaults(handler=_cmd_proxies_remove)

    proxies_reset = proxy_actions.add_parser(
        "reset", help="Reset trusted proxies to local-only defaults (127.0.0.1 and ::1)."
    )
    proxies_reset.set_defaults(handler=_cmd_proxies_reset)

    proxies_clear = proxy_actions.add_parser(
        "clear",
        help="Clear trusted proxies (forwarded headers will be ignored for all /metrics clients).",
    )
    proxies_clear.set_defaults(handler=_cmd_proxies_clear)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    try:
        return int(handler(args))
    except ValueError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
