"""
Functions for aeronautics in this module

- physical quantities always in SI units
- lat,lon,course and heading in degrees

International Standard Atmosphere
::

    p,rho,T = atmos(H)    # atmos as function of geopotential altitude H [m]
    a = vsound(H)         # speed of sound [m/s] as function of H[m]
    p = pressure(H)       # calls atmos but returns only pressure [Pa]
    T = temperature(H)    # calculates temperature [K]
    rho = density(H)      # calls atmos but returns only pressure [Pa]

Speed conversion at altitude H[m] in ISA
::

    Mach = tas2mach(Vtas,H)    # true airspeed (Vtas) to mach number conversion
    Vtas = mach2tas(Mach,H)    # mach number to true airspeed (Vtas) conversion
    Vtas = eas2tas(Veas,H)     # equivalent airspeed to true airspeed, H in [m]
    Veas = tas2eas(Vtas,H)     # true airspeed to equivent airspeed, H in [m]
    Vtas = cas2tas(Vcas,H)     # Vcas  to Vtas conversion both m/s, H in [m]
    Vcas = tas2cas(Vtas,H)     # Vtas to Vcas conversion both m/s, H in [m]
    Vcas = mach2cas(Mach,H)    # Mach to Vcas conversion Vcas in m/s, H in [m]
    Mach   = cas2mach(Vcas,H)  # Vcas to mach copnversion Vcas in m/s, H in [m]

"""

import numpy as np

"""Aero and geo Constants """
kts = 0.514444  # knot -> m/s
ft = 0.3048  # ft -> m
fpm = 0.00508  # ft/min -> m/s
inch = 0.0254  # inch -> m
sqft = 0.09290304  # 1 square foot
nm = 1852  # nautical mile -> m
lbs = 0.453592  # pound -> kg
g0 = 9.80665  # m/s2, Sea level gravity constant
R = 287.05287  # m2/(s2 x K), gas constant, sea level ISA
p0 = 101325  # Pa, air pressure, sea level ISA
rho0 = 1.225  # kg/m3, air density, sea level ISA
T0 = 288.15  # K, temperature, sea level ISA
gamma = 1.40  # cp/cv for air
gamma1 = 0.2  # (gamma-1)/2 for air
gamma2 = 3.5  # gamma/(gamma-1) for air
beta = -0.0065  # [K/m] ISA temp gradient below tropopause
r_earth = 6371000  # m, average earth radius
a0 = 340.293988  # m/s, sea level speed of sound ISA, sqrt(gamma*R*T0)


def atmos(H):
    # H in metres
    T = np.maximum(288.15 - 0.0065 * H, 216.65)
    rhotrop = 1.225 * (T / 288.15) ** 4.256848030018761
    dhstrat = np.maximum(0.0, H - 11000.0)
    rho = rhotrop * np.exp(-dhstrat / 6341.552161)
    p = rho * R * T
    return p, rho, T


def temperature(H):
    p, r, T = atmos(H)
    return T


def pressure(H):
    p, r, T = atmos(H)
    return p


def density(H):
    p, r, T = atmos(H)
    return r


def vsound(H):
    """Speed of sound"""
    T = temperature(H)
    a = np.sqrt(gamma * R * T)
    return a


def distance(lat1, lon1, lat2, lon2, H=0):
    """
    Compute spherical distance from spherical coordinates.

    For two locations in spherical coordinates
    (1, theta, phi) and (1, theta', phi')
    cosine( arc length ) =
       sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    distance = rho * arc length
    """

    # phi = 90 - latitude
    phi1 = np.radians(90 - lat1)
    phi2 = np.radians(90 - lat2)

    # theta = longitude
    theta1 = np.radians(lon1)
    theta2 = np.radians(lon2)

    cos = np.sin(phi1) * np.sin(phi2) * np.cos(theta1 - theta2) + np.cos(phi1) * np.cos(
        phi2
    )
    cos = np.where(cos > 1, 1, cos)

    arc = np.arccos(cos)
    dist = arc * (r_earth + H)  # meters, radius of earth
    return dist


def bearing(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    x = np.sin(lon2 - lon1) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(lon2 - lon1)
    initial_bearing = np.arctan2(x, y)
    initial_bearing = np.degrees(initial_bearing)
    bearing = (initial_bearing + 360) % 360
    return bearing


# -----------------------------------------------------
# Speed conversions, altitude H all in meters
# -----------------------------------------------------
def tas2mach(Vtas, H):
    """True Airspeed to Mach number"""
    a = vsound(H)
    Mach = Vtas / a
    return Mach


def mach2tas(Mach, H):
    """Mach number to True Airspeed"""
    a = vsound(H)
    Vtas = Mach * a
    return Vtas


def eas2tas(Veas, H):
    """Equivalent Airspeed to True Airspeed"""
    rho = density(H)
    Vtas = Veas * np.sqrt(rho0 / rho)
    return Vtas


def tas2eas(Vtas, H):
    """True Airspeed to Equivalent Airspeed"""
    rho = density(H)
    Veas = Vtas * np.sqrt(rho / rho0)
    return Veas


def cas2tas(Vcas, H):
    """Calibrated Airspeed to True Airspeed"""
    p, rho, T = atmos(H)
    qdyn = p0 * ((1 + rho0 * Vcas * Vcas / (7 * p0)) ** 3.5 - 1.0)
    Vtas = np.sqrt(7 * p / rho * ((1 + qdyn / p) ** (2 / 7.0) - 1.0))
    return Vtas


def tas2cas(Vtas, H):
    """True Airspeed to Calibrated Airspeed"""
    p, rho, T = atmos(H)
    qdyn = p * ((1 + rho * Vtas * Vtas / (7 * p)) ** 3.5 - 1.0)
    Vcas = np.sqrt(7 * p0 / rho0 * ((qdyn / p0 + 1.0) ** (2 / 7.0) - 1.0))
    return Vcas


def mach2cas(Mach, H):
    """Mach number to Calibrated Airspeed"""
    Vtas = mach2tas(Mach, H)
    Vcas = tas2cas(Vtas, H)
    return Vcas


def cas2mach(Vcas, H):
    """Calibrated Airspeed to Mach number"""
    Vtas = cas2tas(Vcas, H)
    Mach = tas2mach(Vtas, H)
    return Mach
