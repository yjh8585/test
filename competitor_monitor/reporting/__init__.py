"""Reporting package: Markdown + HTML report generation.

Public API
----------
render_markdown  Build a Korean weekly Markdown report from the analysis dict.
render_html      Convert Markdown text to a self-contained HTML document.
write_report     Persist both formats to settings.report_dir; returns file paths.
"""
from __future__ import annotations

from competitor_monitor.reporting.report import render_html, render_markdown, write_report

__all__ = ["render_markdown", "render_html", "write_report"]
