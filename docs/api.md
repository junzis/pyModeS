# API Reference

## Top-level

::: pyModeS.decode

Use `decode(msg, uplink=True)` for ground-to-air Mode-S interrogations.
This applies to single messages and lists. Results contain `uf` instead
of `df`. See the [uplink migration table](migration.md#mode-s-uplink-interrogations)
for the decoded fields and the mapping from v2 helpers.

## Core types

::: pyModeS.Message

::: pyModeS.Decoded

## Streaming decoder

::: pyModeS.PipeDecoder

## Errors

::: pyModeS.DecodeError

::: pyModeS.InvalidHexError

::: pyModeS.InvalidLengthError

::: pyModeS.UnknownDFError

## Position

::: pyModeS.position.airborne_position_with_ref

::: pyModeS.position.airborne_position_pair

::: pyModeS.position.surface_position_with_ref

::: pyModeS.position.surface_position_pair

::: pyModeS.position.cprNL

::: pyModeS.position.resolve_surface_ref
