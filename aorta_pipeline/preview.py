"""Read-only dataset summaries used by the interactive configuration GUI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .filtering import finite_difference_velocity
from .io import read_trajectories


@dataclass(frozen=True)
class Histogram:
    counts: np.ndarray
    edges: np.ndarray
    minimum: float
    maximum: float
    median: float


@dataclass(frozen=True)
class FilterPreview:
    length: Histogram
    speed_um_per_frame: Histogram
    sample_positions: np.ndarray
    point_count: int
    track_count: int


def _histogram(values: np.ndarray, bins: int = 120) -> Histogram:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        raise ValueError("Cannot display an empty distribution")
    low, high = float(values.min()), float(values.max())
    plot_low, plot_high = low, high
    if plot_high <= plot_low:
        padding = max(0.5, abs(plot_low) * 0.01)
        plot_low, plot_high = plot_low - padding, plot_high + padding
    counts, edges = np.histogram(values, bins=bins, range=(plot_low, plot_high))
    return Histogram(counts, edges, low, high, float(np.median(values)))


def compute_filter_preview(raw_input: Path, *, maximum_display_points: int = 30_000) -> FilterPreview:
    table = read_trajectories(raw_input)
    if table.empty:
        raise ValueError("The selected trajectory dataset is empty")
    lengths = table.groupby("trajid").size().to_numpy(float)
    velocity_table = finite_difference_velocity(table)
    speeds = velocity_table["speed_fd"].to_numpy(float) * 1e6
    positions = table[["x", "y", "z"]].to_numpy(float)
    if len(positions) > maximum_display_points:
        indices = np.linspace(0, len(positions) - 1, maximum_display_points, dtype=int)
        positions = positions[indices]
    return FilterPreview(
        length=_histogram(lengths),
        speed_um_per_frame=_histogram(speeds),
        sample_positions=positions,
        point_count=len(table),
        track_count=int(table["trajid"].nunique()),
    )
