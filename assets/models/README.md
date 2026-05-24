# Model Conventions

## Purpose

This folder stores curated external models and project-authored model assets.

## Rules

- Imported models must be logged in `assets/ASSET_LEDGER.md`.
- Project-authored generated models should also be logged.
- Gameplay collision should be authored separately from visual meshes.
- Prefer wrapper scenes under `scenes/props/`, `scenes/landmarks/`, or `scenes/ship/`.
- Do not edit imported source files in place unless the modification is documented.
- Keep pivots practical: object base near local origin, local `Y` as up where possible.

## Current Folders

- `assets/models/props/`: reusable prop and surface-dressing meshes.
- `assets/models/landmarks/`: landmark and hero-prop meshes.
- `assets/models/ship/placeholders/`: temporary ship model candidates.
