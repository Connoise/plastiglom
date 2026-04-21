"""Opus-driven analyzer. See §7.6 of DESIGN.md.

Produces weekly, monthly, and ad-hoc reports. Never overwrites prior analysis.
Corrections produce a superseding report plus a pointer in `analysis_history/`.
"""

from plastiglom.apps.analyzer.analyzer import AnalysisRequest, Analyzer, Cadence

__all__ = ["AnalysisRequest", "Analyzer", "Cadence"]
