from __future__ import annotations

import argparse
from pathlib import Path

from .eulerian import run_eulerian
from .filtering import run_filtration
from .lagrangian import run_cohorts, run_extension
from .settings import load_settings, require_files
from .validation import run_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aorta-pipeline", description="Reproduce the aortic-phantom trajectory-processing results."
    )
    parser.add_argument("stage", choices=["filter", "eulerian", "extend", "cohorts", "validate", "all"])
    parser.add_argument("--input", type=Path, help="Raw trajectories (.zarr, .parquet, or .csv). Required for filter/all.")
    parser.add_argument("--run-dir", type=Path, default=Path("run"), help="Isolated work/results directory (default: ./run).")
    parser.add_argument("--config", type=Path, help="JSON settings override; unspecified values retain the included defaults.")
    parser.add_argument("--trajectory-file", type=Path,
                        help="Filtered Parquet input for stages after filter (default: RUN_DIR/work/filtered/trajectories.parquet).")
    parser.add_argument("--track-limit", type=int, help="Limit extension tracks for a smoke run.")
    parser.add_argument("--workers", type=int, help="Override extension process count.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_settings(args.config)
    require_files(config, ("roi", "initial_chamber", "crossing_lines", "exclusion_lines"))
    run_dir = args.run_dir.resolve()
    trajectory_path = (args.trajectory_file or run_dir / "work" / "filtered" / "trajectories.parquet").resolve()
    if args.stage in {"filter", "all"}:
        if args.input is None:
            raise SystemExit("--input is required for filter and all")
        outputs = run_filtration(args.input.resolve(), run_dir, config)
        trajectory_path = outputs["trajectories"]
        print(f"filtered trajectories: {trajectory_path}")
    if args.stage in {"eulerian", "all"}:
        print(f"Eulerian series: {run_eulerian(trajectory_path, run_dir, config)}")
    if args.stage in {"extend", "all"}:
        print(f"Lagrangian partitions: {run_extension(trajectory_path, run_dir, config, track_limit=args.track_limit, workers=args.workers)}")
    if args.stage in {"cohorts", "all"}:
        for name, path in run_cohorts(trajectory_path, run_dir, config).items():
            print(f"{name} series: {path}")
    if args.stage in {"validate", "all"}:
        print(f"validation results: {run_validation(trajectory_path, run_dir, config)}")
    return 0
