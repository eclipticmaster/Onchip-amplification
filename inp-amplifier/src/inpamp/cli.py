import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from .config import Config, load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description="YAML-driven Lumerical InP amplifier workflow (plus optional Python reference models)")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["validate", "run", "check"]:
        help_text = {"run": "optional Python reference workflow, not a Lumerical simulation", "check": "optional Python SOA/mode refinement check", "validate": "validate YAML for either workflow"}[command]
        item = sub.add_parser(command, help=help_text)
        item.add_argument("config", type=Path)
        item.add_argument("--set", dest="overrides", action="append", default=[], metavar="SECTION.PARAMETER=VALUE")
        if command == "run":
            item.add_argument("--output", type=Path)
            item.add_argument("--check", action="store_true", help="also run SOA/ASE/mode grid refinement checks")
    for command in ["export-lumerical", "run-lumerical", "inspect-interconnect"]:
        item = sub.add_parser(command)
        item.add_argument("config", type=Path)
        item.add_argument("--set", dest="overrides", action="append", default=[], metavar="SECTION.PARAMETER=VALUE")
        if command != "inspect-interconnect":
            item.add_argument("--output", type=Path, required=True)
        if command != "export-lumerical":
            item.add_argument("--api-path", help="folder containing Ansys-provided lumapi.py")
        if command == "run-lumerical":
            item.add_argument("--solver", choices=["mode", "fdtd", "interconnect"], required=True)
        if command == "inspect-interconnect":
            item.add_argument("--template", type=Path, required=True)
    schema = sub.add_parser("schema", help="emit JSON schema for YAML editor completion")
    schema.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            generated = Config.model_json_schema()
            generated["properties"]["extends"] = {"type": "string", "description": "Parent YAML file, resolved relative to this file"}
            text = json.dumps(generated, indent=2) + "\n"
            if args.output:
                args.output.write_text(text)
            else:
                print(text, end="")
            return 0
        c = load_config(args.config, args.overrides)
        if args.command == "validate":
            print(f"Valid: {args.config} ({c.parameter_status} parameters)")
            return 0
        if args.command == "export-lumerical":
            from .lumerical import export_lumerical
            print(json.dumps(export_lumerical(c, args.output), indent=2))
            return 0
        if args.command == "run-lumerical":
            from .lumerical import run_lumerical
            result = run_lumerical(c, args.solver, args.output, api_path=args.api_path,
                                   config_directory=args.config.resolve().parent)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "inspect-interconnect":
            from .lumerical import inspect_interconnect
            print(json.dumps(inspect_interconnect(c, template=args.template, api_path=args.api_path), indent=2))
            return 0
        from .workflow import convergence_checks, run

        if args.command == "check":
            result = convergence_checks(c)
            print(json.dumps(result, indent=2))
            if not result["passed"]:
                raise SystemExit(1)
            return 0
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = args.output or Path("results") / f"{args.config.stem}-{timestamp}"
        result = run(c, output, check=args.check)
        print(json.dumps({k: result[k] for k in ["amplifier", "microcomb"] if k in result}, indent=2))
        if args.check and not result["numerical_checks"]["passed"]:
            raise SystemExit(1)
        return 0
    except (ValueError, ValidationError, RuntimeError, OSError, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)
