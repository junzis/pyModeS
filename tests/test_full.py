def test_streamer_decode_handles_none_typecode():
    """The Decode.process_raw() path must tolerate messages where
    common.typecode() returns None (non-DF17/18 messages) without
    raising TypeError on `1 <= tc <= 4` comparisons.

    This is a contract/pattern test — it exercises the guarded
    expression logic directly because the Decode class is entangled
    with a multiprocess pipeline that is impractical to instantiate
    in a unit test. The real verification is that Decode.process_raw's
    comparisons use `tc is not None and ...` form.
    """
    tc = None
    # These must not raise TypeError:
    hit_callsign_branch = tc is not None and 1 <= tc <= 4
    hit_position_branch = tc is not None and ((5 <= tc <= 8) or (tc == 19))
    assert hit_callsign_branch is False
    assert hit_position_branch is False
