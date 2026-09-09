from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aorta_pipeline.eulerian import run_eulerian
from aorta_pipeline.filtering import run_filtration
from aorta_pipeline.lagrangian import run_cohorts, run_extension
from aorta_pipeline.settings import load_settings
from aorta_pipeline.synthetic import generate_synthetic_dataset
from aorta_pipeline.validation import run_validation


def test_small_raw_zarr_to_all_result_families(tmp_path):
    created = generate_synthetic_dataset(tmp_path / "synthetic")
    raw_path = created["zarr"]
    settings = load_settings(created["config"])
    settings["extension"].update(maximum_duration_frames=4, workers=1, chunk_size=4)
    settings["validation"].update(number_of_tracks=2,
                                   truncation_fractions=[0.5], maximum_duration_frames=4)
    outputs = run_filtration(raw_path, tmp_path, settings)
    trajectory_path = outputs["trajectories"]
    assert trajectory_path.is_file()
    filtration_report = json.loads((tmp_path / "work" / "filtered" / "filtration_summary.json").read_text())
    assert filtration_report["length_range_points"] == [20, 200]
    assert filtration_report["speed_range_um_per_frame"] == [0.0, 1300.0]
    assert (tmp_path / "results" / "filtered_trajects" / "roi_filtered_trajectories.vtp").is_file()
    assert run_eulerian(trajectory_path, tmp_path, settings).is_file()
    assert run_extension(trajectory_path, tmp_path, settings, track_limit=8, workers=1).is_dir()
    lagrangian_outputs = run_cohorts(trajectory_path, tmp_path, settings)
    assert set(lagrangian_outputs) == {"full_paths", "cohorts", "line_conditions"}
    assert all(path.is_file() for path in lagrangian_outputs.values())
    line_diagnostics = (tmp_path / "work" / "lagrangian" / "line_condition_cohorts.csv").read_text()
    assert "cross_line_1" in line_diagnostics and "cond1" in line_diagnostics
    validation = run_validation(trajectory_path, tmp_path, settings)
    assert (validation / "case_summaries.csv").is_file()
    assert (validation / "figures" / "error_vs_elapsed_time.png").is_file()


def test_entry_script_runs_outside_package_directory(tmp_path):
    script = Path(__file__).resolve().parents[1] / "run_pipeline.py"
    completed = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "eulerian" in completed.stdout
