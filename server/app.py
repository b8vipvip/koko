"""Unified WSGI entrypoint for gunicorn.

The legacy project historically ran two Flask files on different ports:
- kugo_mergedl.py: admin/query/code-management APIs (port 9999)
- app_optimized-cdp.py: Selenium-backed submit/SMS APIs (port 5000)

This module keeps those legacy route implementations intact while exposing a
single ``app`` object for production servers such as gunicorn.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from kugo_mergedl import app as app  # re-exported WSGI app


def _load_legacy_submit_app():
    module_path = Path(__file__).with_name("app_optimized-cdp.py")
    spec = importlib.util.spec_from_file_location("koko_legacy_submit", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load legacy submit app from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def _merge_routes(source_app):
    """Register non-duplicate legacy routes onto the main Flask app."""
    existing_rules = {rule.rule for rule in app.url_map.iter_rules()}
    for rule in source_app.url_map.iter_rules():
        if rule.endpoint == "static" or rule.rule in existing_rules:
            continue
        view_func = source_app.view_functions[rule.endpoint]
        endpoint = f"legacy_submit.{rule.endpoint}"
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        app.add_url_rule(rule.rule, endpoint=endpoint, view_func=view_func, methods=methods)


_merge_routes(_load_legacy_submit_app())
