"""Native Ansys orchestration and independent offline plotting."""
import argparse
import json
import sys
from pathlib import Path

import yaml

from .config import Config, load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lumerical-only simulation; Python configures, launches and plots exported data")
    sub = parser.add_subparsers(dest="command", required=True)
    for command, aliases, help_text in [
        ("validate", [], "validate native YAML inputs"),
        ("export", ["export-lumerical"], "generate Lumerical scripts without running a solver"),
        ("run", ["run-lumerical"], "run a licensed Lumerical solver; no Python simulation fallback"),
        ("sweep", [], "run/export native Lumerical cases from a YAML sweep"),
        ("inspect-interconnect", [], "inspect native template properties and results"),
    ]:
        item = sub.add_parser(command, aliases=aliases, help=help_text)
        item.add_argument("config", type=Path)
        item.add_argument("--set", dest="overrides", action="append", default=[], metavar="SECTION.PARAMETER=VALUE")
        if command in {"export", "run", "sweep"}:
            item.add_argument("--output", type=Path, required=True)
        if command in {"run", "sweep", "inspect-interconnect"}:
            item.add_argument("--api-path", help="directory containing Ansys-provided lumapi.py")
        if command == "run":
            item.add_argument("--solver", choices=["mode", "fdtd", "interconnect"], required=True)
        if command == "sweep":
            item.add_argument("--name", required=True)
            item.add_argument("--export-only", action="store_true", help="export each native case for running in the GUI")
        if command == "inspect-interconnect":
            item.add_argument("--template", type=Path, required=True)
    item = sub.add_parser("plot", help="plot existing native result files offline; never launch a solver")
    item.add_argument("directory", type=Path)
    item.add_argument("--solver", choices=["mode", "fdtd", "interconnect"], required=True)
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--result", help="native .mat or .json file, relative to the result directory")
    item.add_argument("--x", dest="x_field", help="dot-separated native x dataset field")
    item.add_argument("--y", dest="y_field", help="dot-separated native y dataset field")
    item.add_argument("--xlabel", dest="x_label")
    item.add_argument("--ylabel", dest="y_label")
    item.add_argument("--component", choices=["real", "imag", "abs"])
    item = sub.add_parser("plot-sweep", help="graph one exported native measurement from each sweep case")
    item.add_argument("directory", type=Path)
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--result", required=True)
    item.add_argument("--field", required=True)
    item.add_argument("--ylabel", dest="y_label")
    item = sub.add_parser("inspect-results", help="list data paths/shapes in native .mat or .json files offline")
    item.add_argument("file", type=Path)
    item = sub.add_parser("schema", help="emit the native YAML JSON schema")
    item.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    command = {"export-lumerical": "export", "run-lumerical": "run"}.get(args.command, args.command)
    try:
        if command == "schema":
            generated = Config.model_json_schema()
            generated["properties"]["extends"] = {"type": "string", "description": "Parent YAML, relative to this file"}
            text = json.dumps(generated, indent=2) + "\n"
            if args.output:
                args.output.write_text(text)
            else:
                print(text, end="")
            return 0
        if command in {"plot", "plot-sweep", "inspect-results"}:
            from .results import describe_results, plot_native, plot_sweep
            if command == "plot":
                result = plot_native(args.directory, args.solver, args.output, result=args.result,
                                     x_field=args.x_field, y_field=args.y_field, x_label=args.x_label,
                                     y_label=args.y_label, component=args.component)
            elif command == "plot-sweep":
                result = plot_sweep(args.directory, args.output, result=args.result, field=args.field, y_label=args.y_label)
            else:
                result = describe_results(args.file)
            print(json.dumps(result, indent=2))
            return 0
        c = load_config(args.config, args.overrides)
        if command == "validate":
            print(f"Valid native Lumerical configuration: {args.config}")
            return 0
        from .lumerical import export_lumerical, inspect_interconnect, run_lumerical
        if command == "export":
            result = export_lumerical(c, args.output)
        elif command == "run":
            result = run_lumerical(c, args.solver, args.output, api_path=args.api_path,
                                   config_directory=args.config.resolve().parent)
        elif command == "sweep":
            from .workflow import run_sweep
            result = run_sweep(c, args.name, args.output, api_path=args.api_path,
                               config_directory=args.config.resolve().parent, export_only=args.export_only)
        else:
            result = inspect_interconnect(c, template=args.template, api_path=args.api_path)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)
