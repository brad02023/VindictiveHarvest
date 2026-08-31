from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from viha import __app_name__, __app_short__, __version__
from viha.collectors.registry import COLLECTORS
from viha.core.casefile import save_case
from viha.core.harvest import harvest
from viha.core.models import Seed
from viha.export.case_md import render_markdown
from viha.export.graphml import render_graphml


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="viha", description=f"{__app_short__} — {__app_name__}")
    parser.add_argument("--version", action="version", version=f"{__app_short__} {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    reap = sub.add_parser("reap", help="Run a headless harvest")
    reap.add_argument("--name", default="")
    reap.add_argument("--phone", default="")
    reap.add_argument("--email", default="")
    reap.add_argument("--org", default="")
    reap.add_argument("--city", default="")
    reap.add_argument("--state", default="")
    reap.add_argument("--username", default="")
    reap.add_argument("--collectors", default="", help="Comma-separated collector ids")
    reap.add_argument("--out", default="", help="Write JSON here")
    reap.add_argument("--md", default="", help="Write Markdown here")
    reap.add_argument("--graphml", default="", help="Write GraphML here")
    reap.add_argument("--list-collectors", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd is None:
        from viha.app import run_app

        return run_app()

    if args.cmd == "reap":
        if args.list_collectors:
            for c in COLLECTORS:
                print(f"{c.id}\t{c.label}\t{c.blurb}".encode("ascii", "replace").decode("ascii"))
            return 0
        selected = [x.strip() for x in args.collectors.split(",") if x.strip()] or None
        seed = Seed(
            full_name=args.name,
            phone=args.phone,
            email=args.email,
            org=args.org,
            city=args.city,
            state=args.state,
            username=args.username,
        )
        case = harvest(seed, selected=selected, on_log=lambda m: print(m, file=sys.stderr))
        payload = case.to_dict()
        if args.out:
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            print(json.dumps(payload, indent=2))
        if args.md:
            Path(args.md).write_text(render_markdown(case), encoding="utf-8")
        if args.graphml:
            Path(args.graphml).write_text(render_graphml(case), encoding="utf-8")
        save_case(case)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
