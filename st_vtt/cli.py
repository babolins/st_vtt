"""Command line entry point: `st-vtt serve`, `st-vtt validate`, `st-vtt schema`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .content import ContentError, json_schema, load_content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="st-vtt", description="Sheet-first virtual tabletop.")
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Run the server (default).")
    serve.add_argument("-c", "--config", default="config.json")
    serve.add_argument("--reload", action="store_true", help="Auto-reload on code changes (development).")

    validate = sub.add_parser("validate", help="Validate a content pack directory or file.")
    validate.add_argument("path", nargs="?", help="Content pack path (default: from config).")
    validate.add_argument("-c", "--config", default="config.json")

    schema = sub.add_parser("schema", help="Print the content pack JSON Schema.")
    schema.add_argument("-o", "--output", help="Write to a file instead of stdout.")

    args = parser.parse_args(argv)
    cmd = args.cmd or "serve"
    try:
        if cmd == "validate":
            path = args.path
            if not path:
                path = load_config(args.config).content_path
            pack = load_content(path)
            print(f"OK: {pack.pack.name} ({pack.pack.id})")
            print(f"  playbooks: {', '.join(p.id for p in pack.playbooks) or '-'}")
            print(f"  inserts: {', '.join(i.id for i in pack.inserts) or '-'}")
            print(f"  moves: {len(pack.all_moves())}  arcana: {len(pack.arcana)}  shared sheets: {', '.join(t.id for t in pack.shared_sheets) or '-'}")
            return 0
        if cmd == "schema":
            text = json.dumps(json_schema(), indent=2)
            if args.output:
                Path(args.output).write_text(text + "\n", encoding="utf-8")
                print(f"wrote {args.output}")
            else:
                print(text)
            return 0
        # serve, the default
        cfg = load_config(args.config)
        load_content(cfg.content_path)  # fail fast with a readable error
        import uvicorn

        if args.reload:
            import os

            os.environ["ST_VTT_CONFIG"] = str(Path(args.config).resolve())
            uvicorn.run("st_vtt.main:create_app", factory=True, host=cfg.host, port=cfg.port, reload=True)
        else:
            from .main import create_app

            uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port)
        return 0
    except (ConfigError, ContentError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
