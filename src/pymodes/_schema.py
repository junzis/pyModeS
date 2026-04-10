"""Canonical field schema for pymodes Decoded results.

`_FULL_SCHEMA` declares every key that any pyModeS decoder may emit.
It serves two purposes:

1. The `full_dict=True` mode populates missing keys with explicit
   `None` so callers get a uniform shape regardless of message type.
2. A drift-detection test (`tests/test_schema.py`) runs every test
   message in the suite and asserts no decoder ever emits a key not
   declared here.

The type annotations on the right side are documentation only --
runtime ignores them. Use bare `type` for "always present in this
context" and string-form unions like `"int | None"` for optional.
"""

_FULL_SCHEMA: dict[str, type | str] = {
    # --- Always present ---------------------------------------------
    "df": int,
    "icao": str,
    # --- DF17/18/20/21 ----------------------------------------------
    "crc_valid": "bool | None",
    # --- DF20/21 only -----------------------------------------------
    "icao_verified": "bool | None",
    # --- DF4/5/20/21 surveillance reply header ----------------------
    "altitude": "int | None",
    "squawk": "str | None",
    "flight_status": "int | None",
    "downlink_request": "int | None",
    "utility_message": "int | None",
    # --- DF11 all-call reply ----------------------------------------
    "capability": "int | None",
    # --- DF0/16 ACAS ------------------------------------------------
    "vertical_status": "int | None",
    "sensitivity_level": "int | None",
    "reply_information": "int | None",
    "acas_ra_advisory": "dict | None",
    # --- DF17/18 ADS-B common ---------------------------------------
    "typecode": "int | None",
    "bds": "str | None",
    "bds_candidates": "list[str] | None",
    # --- BDS 0,5 / 0,6 raw CPR --------------------------------------
    "cpr_format": "int | None",
    "cpr_lat": "int | None",
    "cpr_lon": "int | None",
    "surveillance_status": "int | None",
    "nic_b": "int | None",
    "nuc_p": "int | None",
    # --- BDS 0,5 / 0,6 resolved position ----------------------------
    "latitude": "float | None",
    "longitude": "float | None",
    # --- BDS 0,6 surface --------------------------------------------
    "movement": "int | None",
    "track_status": "int | None",
    # --- BDS 0,8 identification -------------------------------------
    "callsign": "str | None",
    "category": "int | None",
    "wake_vortex": "str | None",
    # --- BDS 0,9 velocity -------------------------------------------
    "subtype": "int | None",
    "groundspeed": "float | None",
    "track": "float | None",
    "airspeed": "int | None",
    "airspeed_type": "str | None",
    "vertical_rate": "int | None",
    "vr_source": "str | None",
    "geo_minus_baro": "int | None",
    # --- BDS 1,7 GICB capability ------------------------------------
    "supported_bds": "list[str] | None",
    # --- BDS 3,0 ACAS RA broadcast ----------------------------------
    "ara": "int | None",
    "rac": "int | None",
    "ra_terminated": "bool | None",
    "multiple_threat": "bool | None",
    "threat_type": "int | None",
    "threat_identity": "int | None",
    # --- BDS 4,0 selected vertical intention ------------------------
    "selected_altitude_mcp": "int | None",
    "selected_altitude_fms": "int | None",
    "baro_pressure_setting": "float | None",
    "vnav_mode": "bool | None",
    "altitude_hold_mode": "bool | None",
    "approach_mode": "bool | None",
    "target_altitude_source": "str | None",
    # --- BDS 4,4 met routine ----------------------------------------
    "wind_speed": "float | None",
    "wind_direction": "float | None",
    "static_air_temperature": "float | None",
    "average_static_pressure": "int | None",
    "turbulence_4_4": "int | None",
    "humidity": "float | None",
    # --- BDS 4,5 met hazard -----------------------------------------
    "turbulence": "int | None",
    "wind_shear": "int | None",
    "microburst": "int | None",
    "icing": "int | None",
    "wake_vortex_hazard": "int | None",
    "static_air_temp_45": "float | None",
    "average_static_pressure_45": "int | None",
    "radio_height": "int | None",
    # --- BDS 5,0 track and turn -------------------------------------
    "roll": "float | None",
    "track_rate": "float | None",
    "tas": "int | None",
    # --- BDS 6,0 heading and speed ----------------------------------
    "magnetic_heading": "float | None",
    "ias": "int | None",
    "mach": "float | None",
    "baro_vertical_rate": "int | None",
    "inertial_vertical_rate": "int | None",
    # --- BDS 6,1 aircraft status ------------------------------------
    "emergency_state": "int | None",
    "emergency_squawk": "str | None",
    "acas_ra_broadcast": "bool | None",
    # --- BDS 6,2 target state and status ----------------------------
    "selected_altitude_source": "str | None",
    "selected_altitude_v2": "int | None",
    "baro_setting": "float | None",
    "selected_heading": "float | None",
    "tcas_active": "bool | None",
    "autopilot": "bool | None",
    "vnav_mode_v2": "bool | None",
    "altitude_hold_v2": "bool | None",
    "approach_mode_v2": "bool | None",
    # --- BDS 6,5 operational status ---------------------------------
    "version": "int | None",
    "capability_class": "int | None",
    "operational_mode": "int | None",
    "nic_supplement": "int | None",
    # --- Error envelope (batch / pipe mode) -------------------------
    "error": "str | None",
    "raw_msg": "str | None",
}
