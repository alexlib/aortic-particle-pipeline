"""Create a portable ParaView state for the generated Eulerian PVD series.

Run this with ParaView's ``pvpython``, not ordinary Python. ParaView is a
desktop application and is intentionally not a pip dependency of the pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pvd", type=Path, default=Path("results/eulerian/mean_velocity_timeseries.pvd"))
    parser.add_argument("--output", type=Path, default=Path("results/eulerian/velocity_field.pvsm"))
    args = parser.parse_args()

    from paraview.simple import (  # type: ignore[import-not-found]
        ColorBy,
        GetActiveViewOrCreate,
        PVDReader,
        Render,
        SaveState,
        Show,
    )

    pvd = args.pvd.resolve()
    if not pvd.exists():
        raise SystemExit(f"PVD input does not exist: {pvd}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = PVDReader(registrationName=pvd.name, FileName=str(pvd))
    view = GetActiveViewOrCreate("RenderView")
    display = Show(source, view)
    ColorBy(display, ("CELLS", "speed"))
    display.RescaleTransferFunctionToDataRange(True, False)
    view.ResetCamera()
    Render()
    SaveState(str(args.output.resolve()))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
