"""Native Ansys orchestration and independent offline plotting."""
import argparse
import json
import sys
from pathlib import Path

import yaml

from .config import Config, load_config
from .paths import output_directory


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
            item.add_argument("--output", type=Path, help="optional output folder; default: results/<operation>-<local date/time>")
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
    item.add_argument("--output", type=Path, help="default: a timestamped plot folder inside DIRECTORY")
    item.add_argument("--result", help="native .mat or .json file, relative to the result directory")
    item.add_argument("--x", dest="x_field", help="dot-separated native x dataset field")
    item.add_argument("--y", dest="y_field", help="dot-separated native y dataset field")
    item.add_argument("--xlabel", dest="x_label")
    item.add_argument("--ylabel", dest="y_label")
    item.add_argument("--component", choices=["real", "imag", "abs"])
    item = sub.add_parser("plot-sweep", help="graph one exported native measurement from each sweep case")
    item.add_argument("directory", type=Path)
    item.add_argument("--output", type=Path, help="default: a timestamped plot folder inside DIRECTORY")
    item.add_argument("--result", required=True)
    item.add_argument("--field", required=True)
    item.add_argument("--ylabel", dest="y_label")
    item = sub.add_parser("inspect-results", help="list data paths/shapes in native .mat or .json files offline")
    item.add_argument("file", type=Path)
    item = sub.add_parser("figures", help="create editable publication figure exports and an offline gallery from native results")
    item.add_argument("directory", type=Path)
    item.add_argument("--solver", choices=["auto", "mode", "fdtd", "interconnect"], default="auto")
    item.add_argument("--output", type=Path, help="default: DIRECTORY/figures")
    item.add_argument("--style", type=Path, help="editable YAML figure settings and native analyzer mappings")
    item.add_argument("--show", action="store_true", help="open the gallery in your browser")
    item.add_argument("--replace", action="store_true", help="regenerate a previously created figure directory; preserve native data")
    item = sub.add_parser("schema", help="emit the native YAML JSON schema")
    item.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    command = {"export-lumerical": "export", "run-lumerical": "run"}.get(args.command, args.command)
    try:
        if command == "figures":
            from .figures import create_figures
            requested = args.output or args.directory / "figures"
            if not args.replace:
                if args.style is None and (requested / "figures.yaml").is_file():
                    args.style = requested / "figures.yaml"
                args.output = output_directory(requested)
            print(f"Output directory: {(args.output or requested).resolve()}", file=sys.stderr)
            result = create_figures(args.directory, args.output, solver=args.solver,
                                    style_path=args.style, show=args.show, replace=args.replace)
            print(json.dumps(result, indent=2))
            return 0
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
            if command != "inspect-results":
                args.output = output_directory(args.output, root=args.directory,
                                               label=f"{getattr(args, 'solver', 'sweep')}-graphs")
                print(f"Output directory: {args.output}", file=sys.stderr)
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
        if command in {"export", "run", "sweep"}:
            label = "scripts" if command == "export" else args.solver if command == "run" else f"sweep-{args.name}"
            args.output = output_directory(args.output, label=label)
            print(f"Output directory: {args.output}", file=sys.stderr)
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
        if command in {"export", "run", "sweep"}:
            result["output_directory"] = str(args.output)
        if command in {"run", "sweep"} and result.get("status") == "completed" and c.lumerical.make_figures and not getattr(args, "export_only", False):
            # Plotting consumes completed native files; a presentation failure
            # must not turn a successful physical simulation into a failed run.
            try:
                from .figures import create_figures
                style_path = c.lumerical.figure_style
                if style_path:
                    style_path = Path(style_path).expanduser()
                    if not style_path.is_absolute():
                        style_path = args.config.resolve().parent / style_path
                result["figures"] = create_figures(args.output, style_path=style_path,
                                                   show=c.lumerical.show_figures and not c.lumerical.hide_gui)
            except Exception as error:
                result["figures_error"] = str(error)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)
