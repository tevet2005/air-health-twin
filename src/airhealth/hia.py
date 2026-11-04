"""Health impact assessment (HIA) with log-linear concentration-response functions.

For a pollutant concentration ``C`` above a counterfactual ``C0``::

    beta = ln(RR_unit) / unit                      # e.g. RR per 10 µg/m³
    RR   = exp(beta * max(C - C0, 0))
    PAF  = (RR - 1) / RR                           # population attributable fraction
    attributable cases = baseline_rate * population * PAF

All functions are vectorised: scalars, NumPy arrays, pandas objects and
xarray DataArrays (e.g. gridded concentration x gridded population) work.
"""
from __future__ import annotations

import numpy as np


def beta_from_rr(rr: float, unit: float = 10.0) -> float:
    """Slope of the log-linear CRF from a relative risk per ``unit`` increment."""
    if rr <= 0:
        raise ValueError("relative risk must be positive")
    return float(np.log(rr) / unit)


def relative_risk(conc, beta: float, counterfactual: float = 0.0):
    """Relative risk at concentration ``conc``."""
    excess = np.maximum(conc - counterfactual, 0.0)
    return np.exp(beta * excess)


def attributable_fraction(conc, beta: float, counterfactual: float = 0.0):
    """Population attributable fraction, ``1 - 1/RR``."""
    return 1.0 - 1.0 / relative_risk(conc, beta, counterfactual)


def attributable_cases(conc, population, baseline_rate, beta: float, counterfactual: float = 0.0):
    """Cases attributable to exposure above ``counterfactual``.

    ``baseline_rate`` is the observed incidence per person over the period
    (e.g. annual deaths / population).
    """
    return baseline_rate * population * attributable_fraction(conc, beta, counterfactual)
