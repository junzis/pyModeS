"""Minimal ISA (International Standard Atmosphere) helpers.

Exists to support BDS 5,0 / 6,0 Phase 3 disambiguation in the
PipeDecoder: when only ADS-B airborne-velocity (BDS 0,9 subtype
1/2) has been cached for an aircraft, we know its groundspeed
and barometric altitude but not its indicated airspeed or mach
number. Without those, the BDS 6,0 scorer has no matching fields
against its ``known=`` state and can never win a tie against
BDS 5,0. This module converts cached GS+alt into approximate
IAS and mach so the scorer has something to compare against.

Assumptions:

- **Zero wind**: TAS = GS. We don't have wind data in a Mode-S
  stream, and the BDS disambiguation scoring tolerance is
  already ~50 kt (IAS) and ~0.1 mach, so a few dozen knots of
  wind doesn't meaningfully change the winner.
- **ISA model** up to the tropopause (36 089 ft / 11 000 m) with
  the standard 0.0065 K/m lapse rate. Above the tropopause,
  temperature is constant at 216.65 K (isothermal lower
  stratosphere); pressure continues to decay exponentially.
- **Low-Mach IAS approximation**: IAS ≈ TAS · sqrt(rho/rho0).
  Exact within a few knots up to M ≈ 0.6 and within a few
  percent up to M ≈ 0.85, which covers every airliner and
  business-jet cruise envelope. The disambiguation scorer
  tolerates this.

All input altitudes are **feet**, speeds are **knots** — matching
the units PipeDecoder caches from decoded Mode-S output.

This module is internal. A public ``pyModeS.aero`` would be a
natural next step if users ask for these helpers directly, but
until then it stays under the underscore.
"""

from __future__ import annotations

import math

# ISA sea-level reference values (per ICAO Doc 7488 / ISO 2533).
_T0: float = 288.15  # K   — sea-level temperature
_P0: float = 101325.0  # Pa  — sea-level pressure
_RHO0: float = 1.225  # kg/m³ — sea-level density

# ISA lapse and atmospheric constants.
_L: float = 0.0065  # K/m  — lapse rate below tropopause
_R: float = 287.05287  # J/(kg·K) — specific gas constant for dry air
_GAMMA: float = 1.4  # ratio of specific heats for dry air
_G: float = 9.80665  # m/s²  — standard gravity

# Tropopause (top of the linear-lapse troposphere).
_H_TROP: float = 11000.0  # m
_T_TROP: float = _T0 - _L * _H_TROP  # 216.65 K
_P_TROP: float = _P0 * (_T_TROP / _T0) ** (_G / (_L * _R))

# Unit conversions.
_FT_TO_M: float = 0.3048
_KT_TO_MS: float = 0.514444


def isa_temperature(alt_m: float) -> float:
    """ISA temperature at geometric altitude in metres (Kelvin)."""
    if alt_m <= _H_TROP:
        return _T0 - _L * alt_m
    return _T_TROP


def isa_pressure(alt_m: float) -> float:
    """ISA pressure at geometric altitude in metres (Pascals).

    Troposphere: standard power-law from the lapse-rate integral.
    Above the tropopause: exponential decay at constant
    temperature 216.65 K.
    """
    if alt_m <= _H_TROP:
        # Wrap the result in float() because mypy infers the `**`
        # operator with a float base and float exponent as float|complex.
        return float(_P0 * (1.0 - _L * alt_m / _T0) ** (_G / (_L * _R)))
    return _P_TROP * math.exp(-_G * (alt_m - _H_TROP) / (_R * _T_TROP))


def isa_density(alt_m: float) -> float:
    """ISA density at geometric altitude in metres (kg/m³)."""
    return isa_pressure(alt_m) / (_R * isa_temperature(alt_m))


def speed_of_sound(temp_k: float) -> float:
    """Speed of sound at a given temperature in Kelvin (m/s)."""
    return math.sqrt(_GAMMA * _R * temp_k)


def gs_to_ias(gs_kt: float, alt_ft: float) -> float:
    """Approximate IAS from groundspeed, assuming TAS = GS (no wind).

    Uses the low-Mach approximation ``IAS ≈ TAS · sqrt(rho/rho0)``.
    Accurate within a few knots up to cruise speeds on any
    commercial airliner.

    Args:
        gs_kt: Groundspeed (knots), treated as TAS under the
            zero-wind assumption.
        alt_ft: Barometric altitude (feet).

    Returns:
        Indicated airspeed (knots).
    """
    alt_m = alt_ft * _FT_TO_M
    rho = isa_density(alt_m)
    return gs_kt * math.sqrt(rho / _RHO0)


def gs_to_mach(gs_kt: float, alt_ft: float) -> float:
    """Approximate mach number from groundspeed, assuming TAS = GS.

    Args:
        gs_kt: Groundspeed (knots), treated as TAS under the
            zero-wind assumption.
        alt_ft: Barometric altitude (feet).

    Returns:
        Mach number (dimensionless).
    """
    alt_m = alt_ft * _FT_TO_M
    tas_ms = gs_kt * _KT_TO_MS
    a = speed_of_sound(isa_temperature(alt_m))
    return tas_ms / a
