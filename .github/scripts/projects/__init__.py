"""GitHub Projects (v2) tooling for the groomed backlog lifecycle.

A single CLI (``cli.py`` / ``python -m projects``) dispatches every
subcommand across concern-split modules:

- ``config``     — load ``.github/config.json``; repo-root + backlog path.
- ``gh``         — shared ``gh``/GraphQL client (run, batched mutations,
  node-ids, issue list/view, labels, body-refresh, blocking, delete).
- ``board``      — Projects v2 field model (fields, field-map, ensure/create
  fields, set_field, Status/Priority/Size/Points specs).
- ``backlog``    — groomed ``stories`` load/save/id-map/clear + issue-body build.
- ``conversion`` — ``convert``: push the groomed backlog -> issues + board.
- ``state``      — ``list``/``order``/``view``/``status``/``delete``/``delete-all``.
- ``validation`` — ``validate``: groomed ``<REPO-NAME>-NNN`` schema checks.
"""
