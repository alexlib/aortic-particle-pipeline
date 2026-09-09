from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binned_statistic_dd

from .io import write_pvd


def run_eulerian(trajectory_path: Path, run_dir: Path, config: dict) -> Path:
    import pyvista as pv

    settings = config["eulerian"]
    nx, ny, nz = map(int, settings["grid_shape"])
    minimum = int(settings["minimum_samples"])
    window, step = int(settings["window_frames"]), int(settings["step_frames"])
    table = pd.read_parquet(trajectory_path, columns=["time", "x", "y", "z", "vx_fd", "vy_fd", "vz_fd"])
    if table.empty:
        raise ValueError("Cannot form an Eulerian field from an empty table")
    result_dir = Path(run_dir) / "results" / "eulerian"
    series_dir = result_dir / "velocity_timeseries"
    series_dir.mkdir(parents=True, exist_ok=True)

    xyz_all = table[["x", "y", "z"]].to_numpy(float)
    lower, upper = xyz_all.min(axis=0), xyz_all.max(axis=0)
    shape = np.array([nx, ny, nz])
    if np.any(upper <= lower):
        raise ValueError("Eulerian grid requires nonzero extent along x, y, and z")
    edges = [np.linspace(lower[i], upper[i], shape[i] + 1) for i in range(3)]
    spacing = (upper - lower) / shape
    tmin, tmax = int(table["time"].min()), int(table["time"].max())
    centers = list(range(tmin + window // 2, tmax - window // 2 + 1, step))
    if not centers:
        centers = [(tmin + tmax) // 2]
    ordered = table.sort_values("time", kind="mergesort").reset_index(drop=True)
    times = ordered["time"].to_numpy()
    entries: list[tuple[int, str]] = []

    for index, center in enumerate(centers):
        lo, hi = center - window // 2, center + window // 2
        subset = ordered.iloc[np.searchsorted(times, lo, side="left"):np.searchsorted(times, hi, side="right")]
        xyz = subset[["x", "y", "z"]].to_numpy(float)
        velocity = subset[["vx_fd", "vy_fd", "vz_fd"]].to_numpy(float)
        counts, _ = np.histogramdd(xyz, bins=edges)
        components = [binned_statistic_dd(xyz, velocity[:, i], statistic="mean", bins=edges).statistic for i in range(3)]
        valid = counts >= minimum
        components = [np.where(valid, component, np.nan) for component in components]
        speed = np.sqrt(sum(component ** 2 for component in components))
        grid = pv.ImageData(dimensions=(nx + 1, ny + 1, nz + 1), spacing=spacing, origin=lower)
        grid.cell_data["mean_velocity"] = np.stack([c.ravel(order="F") for c in components], axis=1)
        grid.cell_data["speed"] = speed.ravel(order="F")
        grid.cell_data["n_samples"] = counts.ravel(order="F")
        grid.cell_data["valid"] = valid.ravel(order="F").astype(np.uint8)
        name = f"velocity_field_{index:04d}.vti"
        grid.save(series_dir / name)
        entries.append((center, f"velocity_timeseries/{name}"))

    pvd = result_dir / "mean_velocity_timeseries.pvd"
    write_pvd(pvd, entries)
    return pvd
