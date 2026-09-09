# Aortic-phantom particle-processing pipeline

This folder is the minimal, self-contained code package that recreates the
published processing products from raw particle trajectories. Copy this folder
anywhere, install its Python dependencies, and run it without the parent
repository. It contains its geometry selections, numerical defaults, processing
code, desktop GUI, command-line interface, tests, synthetic validation data,
and a small optional ParaView helper. It does **not** contain the multi-gigabyte
experimental source/result data or Git metadata.

## Quick start

Python 3.11 or newer is required. From this folder:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python run_pipeline.py all --input D:\data\trajectories.zarr --run-dir D:\aorta_run
```

For a quick end-to-end trial before the full Lagrangian calculation:

```powershell
python run_pipeline.py filter --input D:\data\trajectories.zarr --run-dir D:\aorta_run
python run_pipeline.py eulerian --run-dir D:\aorta_run
python run_pipeline.py extend --run-dir D:\aorta_run --track-limit 100 --workers 1
python run_pipeline.py cohorts --run-dir D:\aorta_run
python run_pipeline.py validate --run-dir D:\aorta_run
```

`python -m aorta_pipeline` and the installed `aorta-pipeline` command are
equivalent to `python run_pipeline.py`.

## Desktop GUI

Launch the interface from this folder after installation:

```powershell
python launch_gui.py
```

The bundled synthetic input and its lightweight settings are selected when the
GUI first opens. Leave the stage as `all` and click **Run pipeline** for an
immediate end-to-end validation. The interface streams the processing log,
shows whether a job is active, supports stopping the entire worker-process tree,
and opens the selected run's results directory. For real data, replace the raw
input and optionally clear the settings override to restore publication-scale
defaults.

Click **Configure filters & cohorts…** after selecting the raw input. The setup
window reads the data once and provides three focused tabs:

1. **Threshold filters:** the measured trajectory-length distribution and the
   finite-difference speed distribution are shown as logarithmic histograms.
   Drag across either plot, or type values, to set independent lower and upper
   accepted limits.
2. **ROI polygons:** sampled raw positions are displayed in XY, XZ, and YZ.
   Draw an inclusion polygon in any or all planes. A path is retained only when
   every point lies inside every polygon that is enabled; clearing a plane makes
   that projection unconstrained.
3. **Cohorts and lines:** choose the desired Lagrangian products, edit the
   initial-chamber polygons, draw finite crossing/exclusion lines on XY, and add
   named line-cohort rules. Drawn crossing lines are directed from the first
   click to the second and require the user to identify whether the phantom
   interior is on their left or right.

Saving writes a complete, inspectable setup to `RUN_DIR/setup/` and selects its
`pipeline_settings.json` in the main window. The geometry JSON files therefore
travel with that run instead of modifying the bundled defaults.

Use **Create demo data…** to make another deterministic copy in a chosen
location. The GUI then selects the generated Zarr input, settings, and run
directory automatically. Processing runs in a separate Python process so the
window remains responsive and the same tested CLI remains the sole backend.

## Bundled synthetic validation data

`sample_data/trajectories.zarr` contains 64 artificial trajectories with 80
samples each (5,120 rows). Track start frames are staggered to provide
time-resolved Lagrangian support. The paths remain inside the filtration ROI,
stay below the speed cutoff, and traverse the two internal gates from the
initial chamber toward the outlet. `sample_data/synthetic_settings.json` only
reduces grid size, worker count, extension duration, and validation sample size,
and enables the new full-path export alongside all cohort products. It does not
replace the embedded anatomy geometry.

The sample can also be regenerated from the command line:

```powershell
python -m aorta_pipeline.synthetic --output sample_data --seed 7
```

Expected end-to-end checks include 64 surviving filtered tracks, Eulerian VTI
and PVD output, a full-path time series, nonempty chamber-to-exit and line-to-line
cohorts, three line-condition tables, and 18 held-out validation cases. A final
`insufficient_lagrangian_support` status is expected once a reconstructed path
advances beyond the finite synthetic acquisition; matched hidden portions are
still evaluated normally. The data are for software validation only, never for
scientific interpretation.

## Input contract

The preferred raw input is a Zarr group with:

| Array | Shape | Meaning |
|---|---:|---|
| `trajid` | `(N,)` | integer particle/trajectory identifier |
| `time` | `(N,)` | integer acquisition frame |
| `pos` | `(N, 3)` | `x,y,z` position in metres |

Parquet and CSV are also accepted when they contain `trajid,time,x,y,z`.
`track_id` may replace `trajid`, and `frame` may replace `time`. Native velocity
and acceleration arrays are intentionally ignored: velocity is consistently
recomputed from position. Every `(trajid,time)` pair must be unique and every
position finite.

## Processing stages

### 1. Filtration

The `filter` stage exactly orders samples by trajectory and time, then:

1. Retains whole tracks within the configured lower/upper sample count,
   inclusive (published defaults: 10–1,200).
2. Computes velocity in metres/frame using a centred position difference for
   interior samples and one-sided differences at track endpoints.
3. Retains individual samples within the configured lower/upper speed interval
   (published defaults: 0–1,300 µm/frame), then reapplies the selected length
   minimum to affected tracks.
4. Keeps a track only when **all** remaining points are inside every enabled XY,
   XZ, and YZ polygon in `geometry/roi.json`.

The two VTP exports retain the published names. The result directory spelling
`filtered_trajects` is deliberately preserved for compatibility.

### 2. Eulerian flow field

The `eulerian` stage bins the finite-difference velocities onto a fixed
15×15×8 Cartesian cell grid spanning the final filtered data bounds. It uses
500-frame overlapping windows separated by 100 frames. A cell is valid only
with at least 15 samples in that window. Each VTI stores `mean_velocity`,
`speed`, `n_samples`, and `valid`; the PVD uses the window centre frame as its
timestep. Grid geometry is fixed across the series.

This field is a visualization/analysis product. It is never used to reconstruct
Lagrangian paths.

### 3. Lagrangian flow-map extension

The `extend` stage constructs exact one-frame measured pairs
`x_i(t) → x_i(t+1)`. At every virtual step it selects spatial neighbours at the
matching start frame with an adaptive Gaussian kernel. It fits the local map

`d(z) = d0 + G (z - q)`

by weighted ridge least squares and predicts `q_next = q + d0`. If the primary
fit is inadequately supported, it follows one explicit hierarchy: expand the
neighbourhood, strengthen regularization, use a weighted constant displacement,
or reject the step. Acceptance records distinct-track count, effective sample
size, condition number, nearest-support distance, bandwidth, fallback mode, and
a confidence score.

The resulting path combines immutable measured points with points labelled
`virtual_lagrangian`. Prediction is repeated from the newly predicted position
and the next frame until the path crosses the ROI (located by segment bisection),
support/confidence fails, a numerical displacement guard fails, or the
5,000-frame duration ceiling is reached. Paths that do not reach an actual ROI
exit are right-censored and are not assigned an exit time.

Extension output is partitioned by chunk because a full run can contain hundreds
of millions of rows. Existing complete chunk pairs are reused on restart. A
manifest prevents a limited smoke run, changed settings, or changed input from
being silently mixed with old partitions; use a new run directory for a
different run.

### 4. Lagrangian outputs, cohorts, and flow-map visualizations

The `cohorts` stage scans every consecutive measured/reconstructed segment. It
derives:

- chamber-to-exit paths: start in the embedded initial chamber and later cross a
  directed exit line;
- line-to-line paths: have a measured entry crossing and a subsequent exit;
- chamber-stasis paths: start in, and never leave, the initial chamber;
- three published line conditions, with the embedded exclusion lines applied.

These products are independently selectable with `cohorts.enabled_outputs`.
Selecting **Full paths only** exports every measured and reconstructed path to
`full_paths_timeseries.pvd` and returns before loading or evaluating any chamber,
crossing-line, exclusion-line, or retrospective cohort rule.

Custom line cohorts use explicit predicates in `cohorts.line_rules`. Each rule
has an `all_of` list, an `any_of` list, and an optional exclusion-line veto.
Supported predicates are `cross:<line_id>`, `no_exit`, and `first_frame`.
Every `all_of` predicate must hold; when `any_of` is nonempty, at least one of
those predicates must hold. The GUI constructs these rules without requiring
manual JSON editing.

The cohort PVD uses codes `0=chamber_to_exit`, `1=chamber_stasis`, and
`2=line_to_line`; large chamber cohorts are reproducibly sampled to 5,000 tracks
each (seed 0), while line-to-line is kept in full. The line-condition PVD uses
codes 1–3 and no sampling. Per-frame VTP point clouds include track ID,
normalized residence time, and measured/virtual status.

### 5. Long-term validation

The `validate` stage randomly selects up to 300 tracks of at least 200 samples,
removes **all** selected tracks from model support, and truncates each at 25%,
50%, and 75%. It runs the same production extension from each known prefix and
compares predicted points to the hidden measured suffix at matching frames. The
CSV outputs report coverage, absolute position error, and error normalized by
the track's mean measured step. The plot summarizes median and interquartile
normalized error versus elapsed reconstruction time. This tests accumulated
multi-step behavior rather than only one-step interpolation.

## Output layout

```text
RUN_DIR/
├── work/                         # reusable numeric intermediates
│   ├── filtered/
│   │   ├── trajectories.parquet
│   │   ├── trajectory_summary.csv
│   │   └── filtration_summary.json
│   └── lagrangian/
│       ├── points/chunk_*.parquet
│       ├── summary/chunk_*.parquet
│       ├── extension_summary.csv
│       └── cohort/condition tables
└── results/                      # recreates the published result structure
    ├── filtered_trajects/
    │   ├── filtered_trajectories.vtp
    │   └── roi_filtered_trajectories.vtp
    ├── eulerian/
    │   ├── mean_velocity_timeseries.pvd
    │   └── velocity_timeseries/velocity_field_*.vti
    ├── lagrangian/
    │   ├── full_paths_timeseries.pvd       # when full_paths is selected
    │   ├── full_paths_timeseries/frame_*.vtp
    │   ├── cohorts_timeseries.pvd
    │   ├── cohorts_timeseries/frame_*.vtp
    │   ├── line_condition_timeseries.pvd
    │   └── line_condition_timeseries/frame_*.vtp
    └── validation/
        ├── case_summaries.csv
        ├── pointwise_position_errors.csv
        └── figures/error_vs_elapsed_time.png
```

Open a PVD file rather than an individual VTI/VTP to use ParaView's time
controls. A PVSM state is machine/path-specific, so it is generated rather than
shipped. With ParaView installed:

```powershell
pvpython make_paraview_state.py --pvd D:\aorta_run\results\eulerian\mean_velocity_timeseries.pvd --output D:\aorta_run\results\eulerian\velocity_field.pvsm
```

## Configuration and reproducibility

All published numerical settings are in `settings/default.json`; all manually
selected geometry is in `geometry/`. To change only selected values, supply a
JSON override with `--config`. Nested values not mentioned in the override keep
their defaults. Geometry paths in an override resolve relative to that override
file; included default geometry resolves inside this folder.

For publication-scale runs, use a new, empty run directory on a disk with ample
space. The current workload can produce hundreds of millions of Lagrangian
points and several gigabytes of time-series files. Worker processes each hold a
support model; reduce `--workers` if memory is constrained.

Run the package tests with:

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
```

The folder intentionally has one processing backend, one implementation of each
algorithm, no copied experimental result data, and no imports or path references
to its original parent codebase. The GUI invokes that backend rather than
duplicating its algorithms. GitHub publication remains a separate next step.
