# Migrating from pyModeS 2.x to pymodes 3

pymodes 3 is a ground-up rewrite with a cleaner API, faster internals,
and no Cython extension. It is **not backwards-compatible** with
pyModeS 2.x.

The full equivalence table, renamed-keys map, and live-stream
migration examples are added in a follow-up task. For now, if you
aren't ready to migrate:

```sh
pip install "pyModeS<3"
```

Both v2 and v3 coexist on PyPI because they use different import
names (`pyModeS` vs `pymodes`).
