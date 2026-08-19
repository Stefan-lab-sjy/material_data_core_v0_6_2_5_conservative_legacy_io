from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings, clear_local_data_root, local_config_path, write_local_data_root


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Material Agent local data-root configuration")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("path")
    sub.add_parser("reset")
    args = p.parse_args(argv)

    if args.command == "set":
        cfg = write_local_data_root(args.path)
        settings = Settings.load()
        print(f"Config file : {cfg}")
        print(f"Data root   : {settings.data_root}")
        print(f"Catalog     : {settings.db_path}")
        return 0
    if args.command == "reset":
        clear_local_data_root()
        settings = Settings.load()
        print("Local data-root override removed.")
        print(f"Data root   : {settings.data_root}")
        return 0

    settings = Settings.load()
    print(f"Config file : {local_config_path()}")
    print(f"Data root   : {settings.data_root}")
    print(f"Catalog     : {settings.db_path}")
    print(f"Catalog exists: {settings.db_path.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
