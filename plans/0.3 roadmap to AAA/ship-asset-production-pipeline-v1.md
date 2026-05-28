# Ship Asset Production Pipeline v1

## Purpose

The current ship art process has improved the prototype, but the rate of quality gain is too slow because we are editing one-off scene geometry and manually iterating inside Godot. The 0.3 goal is to build a repeatable production pipeline that can produce high-quality ships with coherent exterior and interior detail in short focused sprints.

This document defines the first version of that pipeline.

## Target Outcome

Create a workflow where a new ship can move from references to a playable Godot-integrated prototype in roughly one focused production day.

The one-day target is not final AAA shipping quality. The target is a high-fidelity vertical-slice asset with:

- coherent exterior silhouette
- believable cockpit/canopy design
- matching interior volume
- visible hatch/ramp logic
- authored collision and traversal markers
- strong PBR material separation
- realistic practical lighting
- automated review evidence

## Core Principle

We should stop building ships as Godot scene edits first.

Ships should be authored as asset packages:

- exterior model
- interior model
- collision proxies
- named sockets and gameplay markers
- material set
- light fixtures
- import metadata
- review renders

Godot should consume the package, not be the primary modeling tool.

## Pipeline Overview

### 1. Reference And Brief

Each ship starts with a short art brief:

- role: scout, lander, shuttle, hauler, fighter, science craft
- player affordances: cockpit, hatch, ramp, walkable exterior, cargo bay
- scale target: length, width, interior standing height, cockpit seat size
- visual references: 3-8 images
- material references: hull, floor, glass, rubber, exposed mechanics
- lighting references: cockpit practicals, hatch lights, exterior navigation lights

Acceptance:

- references are saved in `plans` or `references`
- target dimensions are recorded
- human approves the direction before modeling begins

### 2. Source Or Generate Base Candidates

For each ship, produce 3-5 candidates from one or more sources:

- open-source models with compatible licenses
- kitbash assembly from a curated local library
- AI-generated concept/base meshes
- custom Blender blockout

Generated meshes should be treated as starting points, not final production assets. They must be reviewed for topology, scale, UVs, material usability, license, and interior fit.

Acceptance:

- each candidate has preview renders
- each candidate has a source/license note
- human chooses one candidate before integration work starts

### 3. Blender Assembly Scene

The selected ship gets a dedicated Blender source scene.

Required collections:

- `Exterior`
- `Interior`
- `Collision`
- `Markers`
- `Lights`
- `ReviewCameras`
- `Disabled_Source`

Required marker objects:

- `seat_anchor`
- `pilot_eye`
- `seat_exit`
- `interior_spawn`
- `exterior_exit`
- `hatch_center`
- `ramp_start`
- `ramp_end`
- `collision_bounds`

Acceptance:

- exterior and interior are spatially aligned in one Blender scene
- player capsule and seated pilot proxy are visible during authoring
- cockpit canopy and interior pilot view are checked against the exterior model
- hatch/ramp path is visible and traversable in the scene

### 4. Kitbash And Detail Pass

The main quality jump should come from reusable modular details, not manual primitive nudging.

Initial kitbash library should include:

- hull panels
- beveled structural ribs
- cockpit frame parts
- hatch/ramp hinges
- vents and grilles
- exposed pipes/cables
- light housings
- landing gear pieces
- control panels
- seats
- handles and grab rails
- rubber gaskets

Acceptance:

- major surfaces have secondary forms
- paneling follows the ship shape rather than random decoration
- cockpit frame, hatch, and ramp have believable mechanical construction
- details do not block traversal or view

### 5. Material And Texture Pass

Each ship uses a small controlled material family:

- painted hull metal
- darker structural metal
- rubber/gasket material
- glass/canopy material
- worn floor material
- emissive fixture material
- screen/control material

Preferred material workflow:

- Blender procedural/PBR materials for first pass
- Substance Painter or equivalent for higher-end authored texture passes
- shared material naming conventions for Godot import

Acceptance:

- material families read distinctly at gameplay distance
- roughness is controlled and not noisy
- glass is transparent and legible
- emissive fixtures visibly correspond to actual light sources
- floor and hatch materials show wear without visual clutter

### 6. Collision And Traversal Authoring

Collision should be authored as a separate product, not guessed from visual meshes.

Collision deliverables:

- interior walkable floor collision
- ramp/stair collision
- seat/chair obstruction collision
- hatch/ramp threshold collision
- exterior hull walkable collision where intended
- simplified exterior impact collision

Acceptance:

- player can walk hatch to cockpit without clipping or snagging
- player can stand from seat and sit again without imparting ship momentum
- player can exit the ship with inherited ship trajectory
- visual collision debug stays within accepted tolerance of intended surfaces
- collision never exists as large invisible boxes that contradict the visual model

### 7. Godot Import Package

Each ship package exports:

- `ship_exterior.glb`
- `ship_interior.glb`
- `ship_collision.glb`
- `ship_markers.json`
- `ship_material_report.json`
- `ship_asset_report.json`

Godot import scripts should:

- instantiate the exterior visual
- instantiate the interior visual
- build collision nodes from collision meshes
- place markers from JSON
- wire cockpit camera/seat/hatch paths
- assign materials or material overrides
- generate validation metadata

Acceptance:

- no hand-edited marker drift after import
- re-exporting from Blender updates Godot consistently
- generated reports flag missing markers, bad scale, or missing materials

### 8. Automated Evidence

Every meaningful production pass should generate review evidence.

Required evidence:

- exterior turntable MP4
- cockpit view MP4
- hatch entry/exit MP4
- interior walkthrough MP4
- collision overlay screenshots
- scale comparison screenshot with player capsule
- material contact sheet

Evidence should keep only the latest 2-3 timestamped artifacts per review type plus a `current` alias.

Acceptance:

- human can review the asset without launching the game
- evidence shows the exact areas being changed
- stale artifacts are automatically cleaned up

## Tooling Requirements

### Required Now

- Blender on host
- Godot .NET on host
- host MCP profiles for Blender export, Godot import, validation, and review capture
- repo scripts for cleanup of old review artifacts

### Strongly Recommended

- curated local Blender kitbash library
- curated PBR material library
- automated Blender camera/render profiles
- automated geometry reports:
  - object bounds
  - triangle count
  - material count
  - missing UVs
  - missing marker objects
  - collision/visual bounds mismatch

### Optional But Valuable

- AI 3D generation tools for concept/base mesh exploration
- Substance Painter or equivalent for higher-quality PBR texturing
- paid/open asset libraries, only after human license review

## First Production Sprint

The first 0.3 sprint should not try to create every future ship feature.

It should produce one repeatable ship asset package using the current shuttle as the test case.

Sprint deliverables:

- Blender scene reorganized into required collections
- player capsule and seated pilot proxies
- marker export script
- collision export script
- material report script
- Godot import/update script
- exterior/cockpit/interior/hatch review captures
- cleanup script for old review artifacts
- written acceptance checklist

Success means we can change the ship in Blender, run one host profile, and get an updated Godot ship plus review evidence without manual scene surgery.

## Quality Gates

A ship cannot be accepted into the playable prototype unless:

- exterior and interior align spatially
- cockpit view matches exterior canopy design
- hatch and ramp logic are visible and believable
- player traversal validates from hatch to cockpit and back
- standing/sitting does not perturb ship trajectory
- exterior lights have visible fixtures and illuminate nearby geometry
- materials have readable PBR separation
- collision is authored and reviewed
- human has approved source assets and licensing

## Open Questions

- Do we want to pay for higher-end asset libraries or tools such as Substance Painter?
- Do we want generated AI meshes only for concepting, or are we willing to clean them into production assets?
- Should the current shuttle remain the 0.3 pipeline test asset, or should we select a new ship candidate specifically for the pipeline?
- What is the minimum acceptable triangle/material budget for one high-fidelity ship?
- Should ship interiors be physically inside the exterior model, or can some ships use spatial tricks later?

## Recommended Next Step

Write the detailed implementation plan for `0.3.1 Ship Pipeline Foundation`.

That plan should focus on tooling and repeatability before another visual iteration:

- standard Blender collections
- export scripts
- marker schema
- Godot import update
- evidence generation
- artifact cleanup
- validation checklist
