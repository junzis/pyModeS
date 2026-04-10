"""Curated airport database (SEED — replaced by scripts/build_airport_db.py).

This file is a small hand-curated placeholder so the package works
out of the box and tests pass offline. The release build runs
`scripts/build_airport_db.py` to replace this with ~4000-5000
large and medium airports sourced from OurAirports.

Do not edit by hand — rerun the build script to regenerate.
"""

AIRPORTS: dict[str, tuple[float, float]] = {
    "EHAM": (52.30806, 4.76417),  # Amsterdam Schiphol
    "KJFK": (40.63983, -73.77874),  # New York JFK
    "KLAX": (33.94250, -118.40801),  # Los Angeles
    "LFPG": (49.01278, 2.55),  # Paris Charles de Gaulle
    "EGLL": (51.47060, -0.45416),  # London Heathrow
    "NZCH": (-43.48940, 172.53190),  # Christchurch (surface-position test vector)
    "RJTT": (35.55230, 139.78100),  # Tokyo Haneda
    "OMDB": (25.25280, 55.36440),  # Dubai International
    "WSSS": (1.35019, 103.99430),  # Singapore Changi
    "YSSY": (-33.94610, 151.17720),  # Sydney Kingsford Smith
}

AIRPORT_NAMES: dict[str, str] = {
    "EHAM": "Amsterdam Schiphol Airport",
    "KJFK": "John F Kennedy International Airport",
    "KLAX": "Los Angeles International Airport",
    "LFPG": "Charles de Gaulle International Airport",
    "EGLL": "London Heathrow Airport",
    "NZCH": "Christchurch International Airport",
    "RJTT": "Tokyo Haneda International Airport",
    "OMDB": "Dubai International Airport",
    "WSSS": "Singapore Changi Airport",
    "YSSY": "Sydney Kingsford Smith International Airport",
}
