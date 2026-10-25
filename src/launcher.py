"""Single entry point: `nse-pulse-run <eod|ui|oi|fundamentals> [args...]`.

  eod           EOD scraper pipeline (orchestrator CLI; extra args are passed through)
  ui            Streamlit research dashboard (port 8501)
  oi            live options-OI dashboard (FastAPI, port 8000)
  fundamentals  fundamentals web app (FastAPI, port 8001) or its CLI: `fundamentals cli daily`
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _uvicorn(app: str, port: int, extra: list[str]) -> int:
    import uvicorn
    host = extra[0] if extra else "127.0.0.1"
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def cli(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "eod":
        from orchestrator import cli as eod
        sys.argv = ["nse-pulse", *rest]
        return eod() or 0
    if cmd == "ui":
        return subprocess.call([sys.executable, "-m", "streamlit", "run",
                                str(ROOT / "src/webapp/Home.py"),
                                "--server.address", "127.0.0.1", "--server.port", "8501", *rest])
    if cmd == "oi":
        return _uvicorn("src.oipulse.main:app", 8000, rest)
    if cmd == "fundamentals":
        if rest[:1] == ["cli"]:
            from src.fundamentals.main import main
            sys.argv = ["fundamentals", *rest[1:]]
            return main()
        return _uvicorn("src.fundamentals.web.app:app", 8001, rest)
    print(f"unknown command {cmd!r}\n{__doc__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
