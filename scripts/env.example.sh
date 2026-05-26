#!/usr/bin/env bash
# Copy or source .tools/env.sh after running scripts/setup-macos.sh.
# This example documents the variables used by scripts/validate.sh.

export DOTNET_ROOT="/path/to/dotnet"
export PATH="${DOTNET_ROOT}:$PATH"
export GODOT_BIN="/Applications/Godot.app/Contents/MacOS/Godot"
export BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
