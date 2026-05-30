"""Command-line orchestrator.

    python -m competitor_monitor.cli collect    # gather data into SQLite
    python -m competitor_monitor.cli report     # analyze stored data -> report
    python -m competitor_monitor.cli dashboard  # build static HTML dashboard
    python -m competitor_monitor.cli run         # collect + report + dashboard
    python -m competitor_monitor.cli run --demo  # no API keys: load sample data

For the interactive dashboard:  streamlit run dashboard.py

The orchestrator owns persistence: collectors return records, the CLI saves
them. This keeps each source independent and the data flow easy to follow.
"""
from __future__ import annotations

import argparse
import logging
import sys

from .analysis import build_analysis, summarize_creative
from .collectors import build_collectors
from .config import load_secrets, load_settings
from .dashboard_html import write_dashboard
from .fixtures import demo_records
from .reporting import write_report
from .storage import Storage

log = logging.getLogger("competitor_monitor")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def do_collect(storage: Storage, settings, secrets, *, demo: bool) -> int:
    """Run every available collector and persist results. Returns rows saved."""
    if demo:
        log.info("[demo] loading bundled SYNTHETIC sample data (no API calls)")
        return storage.save(demo_records())

    total = 0
    for collector in build_collectors(settings, secrets):
        reason = collector.skip_reason()
        if reason:
            log.warning(reason)
            continue
        log.info("[%s] collecting...", collector.name)
        try:
            records = collector.collect(settings.competitors)
        except Exception as exc:  # a whole source failing must not abort the run
            log.error("[%s] failed: %s", collector.name, exc)
            continue
        saved = storage.save(records)
        log.info("[%s] saved %d records", collector.name, saved)
        total += saved
    if total == 0:
        log.warning(
            "No data collected. Configure API keys (see docs/API_KEYS.md) "
            "or try a no-keys trial: python -m competitor_monitor.cli run --demo"
        )
    return total


def do_report(storage: Storage, settings, secrets) -> dict:
    """Analyze stored data and write the weekly report."""
    log.info("analyzing stored data...")
    analysis = build_analysis(storage)
    llm_summary = summarize_creative(storage, settings, secrets)
    if llm_summary and "error" in llm_summary:
        log.warning("LLM summary failed: %s", llm_summary["error"])
    paths = write_report(analysis, settings, llm_summary=llm_summary)
    log.info("report written: %s", paths["markdown_path"])
    log.info("report written: %s", paths["html_path"])
    return paths


def do_dashboard(storage: Storage, settings) -> dict:
    """Generate the static HTML dashboard and a PNG image from stored data."""
    log.info("building static HTML dashboard...")
    html_path = write_dashboard(storage, settings)
    log.info("dashboard written: %s", html_path)

    # PNG export is optional: it needs matplotlib. Don't fail the run if it's
    # not installed — the HTML dashboard is the primary artifact.
    png_path = None
    try:
        from .dashboard_image import write_dashboard_image
        png_path = write_dashboard_image(storage, settings)
        log.info("dashboard image written: %s", png_path)
    except ImportError:
        log.warning("matplotlib not installed — skipping PNG dashboard image")
    return {"html": html_path, "png": png_path}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="competitor_monitor", description=__doc__)
    p.add_argument("command", choices=["collect", "report", "dashboard", "run"])
    p.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    p.add_argument("--env", default=".env", help="path to .env secrets file")
    p.add_argument("--demo", action="store_true", help="load bundled sample data (no API keys)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)

    settings = load_settings(args.config)
    secrets = load_secrets(args.env)

    with Storage(settings.db_path) as storage:
        # `dashboard --demo` should still seed data so it renders without keys.
        if args.command in ("collect", "run") or (args.command == "dashboard" and args.demo):
            do_collect(storage, settings, secrets, demo=args.demo)
        if args.command in ("report", "run"):
            paths = do_report(storage, settings, secrets)
            print(f"\n✓ Report: {paths['markdown_path']}")
            print(f"✓ HTML:   {paths['html_path']}")
        if args.command in ("dashboard", "run"):
            dash = do_dashboard(storage, settings)
            print(f"✓ Dashboard (HTML): {dash['html']}")
            if dash["png"]:
                print(f"✓ Dashboard (PNG):  {dash['png']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
