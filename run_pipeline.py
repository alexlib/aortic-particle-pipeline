"""Repository-local entry point; equivalent to ``python -m aorta_pipeline``."""

from aorta_pipeline.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
