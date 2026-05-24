# Local Setup

This project is a Godot 4.6 C# project targeting Linux and macOS first.

## Required Tools

Install these on the host Mac:

- Godot **4.6.3 .NET** editor.
- .NET **8 SDK**.
- Git.

Recommended editor:

- Visual Studio Code, JetBrains Rider, or another C# editor.

Optional later:

- Godot export templates.
- Xcode Command Line Tools for macOS signing/notarization workflows.

## Recommended macOS Install

The easiest path is the project-local setup script:

```bash
scripts/setup-macos.sh
source .tools/env.sh
scripts/validate.sh
```

This installs tools under `.tools/`:

- `.tools/dotnet`
- `.tools/godot`
- `.tools/env.sh`

It does not install Godot or .NET globally.

Use the manual steps below if you prefer system-wide installs.

## Manual macOS Install

### 1. Install .NET 8 SDK

Use Microsoft's official .NET 8 SDK installer:

https://dotnet.microsoft.com/en-us/download/dotnet/8.0

Choose:

- macOS Arm64 for Apple Silicon Macs.
- macOS x64 for Intel Macs.

After installation, verify:

```bash
dotnet --info
```

The project currently targets:

```xml
<TargetFramework>net8.0</TargetFramework>
```

So .NET 8 SDK is the known-good baseline.

### 2. Install Godot 4.6.3 .NET

Download the official Godot 4.6.3 .NET build:

https://godotengine.org/download/archive/4.6.3-stable/

Choose:

- macOS
- `.NET`
- Universal build

Move the app to `/Applications` or another stable location.

Important:

- Use the **.NET** Godot build, not the standard build.
- The standard build cannot run this C# project.

### 3. Open the Project

Open Godot 4.6.3 .NET, import this folder, and open:

```text
/app/space-game/project.godot
```

On a normal local checkout, this is the repository root containing `project.godot`.

### 4. Build C#

From the repository root:

```bash
dotnet build SmallSolarSystem.csproj
```

Then open/run the project in Godot.

Main scene:

```text
res://scenes/solar_system/Phase2TestWorld.tscn
```

Validation scene:

```text
res://scenes/solar_system/Phase2Validation.tscn
```

## Homebrew Alternative

Homebrew can install Godot .NET and the .NET SDK:

```bash
brew install --cask godot-mono
brew install --cask dotnet-sdk
```

However, as of May 24, 2026, Homebrew's `godot-mono` cask is listed at 4.6.2 while this project was created and validated against Godot 4.6.3. Use the official Godot archive if you want the exact version.

If Homebrew installs a newer .NET SDK, that may still build `net8.0`, but .NET 8 SDK remains the project baseline.

## Validation Commands

From the repository root:

```bash
dotnet build SmallSolarSystem.csproj
```

If the `godot` executable is available on your `PATH`, run:

```bash
godot --headless --path . --import
godot --headless --path . --quit-after 30 scenes/solar_system/Phase1TestWorld.tscn
godot --headless --path . scenes/solar_system/Phase1Validation.tscn
godot --headless --path . scenes/solar_system/Phase2Validation.tscn
```

If Godot is installed as a macOS app and not on `PATH`, use the executable inside the app bundle:

```bash
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --import
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit-after 30 scenes/solar_system/Phase1TestWorld.tscn
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . scenes/solar_system/Phase1Validation.tscn
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . scenes/solar_system/Phase2Validation.tscn
```

The validation scene should print:

```text
Phase 2 validation passed.
```

## Current Controls

- `WASD`: move.
- Mouse: look.
- `Space`: jump.
- `Left Shift`: jetpack.
- `Control`: zero-g brake.
- `Esc`: release/capture mouse.
- `F3`: toggle debug overlay.

## Export Dependencies

Exports are not required for Phase 1.

When we start exporting builds, install Godot 4.6.3 .NET export templates from inside Godot:

```text
Editor -> Manage Export Templates
```

For Linux desktop exports:

- Godot export templates are enough for basic builds.

For macOS desktop exports:

- Godot export templates are enough for local unsigned builds.
- Xcode Command Line Tools are needed later for signing/notarization workflows.
- An Apple Developer account is needed later for distributing signed/notarized builds outside local testing.

## Not Needed Yet

Do not install these for Phase 1:

- Docker.
- Blender.
- Wwise/FMOD.
- Steamworks SDK.
- Console SDKs.
- Mobile SDKs.
- Web export tooling.

Blender will probably become useful once we need real ship/planet meshes, but placeholder Godot meshes are enough for the current prototype.

## Sources

- Godot C#/.NET documentation: https://docs.godotengine.org/en/stable/getting_started/scripting/c_sharp/index.html
- Godot 4.6.3 official archive: https://godotengine.org/download/archive/4.6.3-stable/
- Microsoft .NET on macOS documentation: https://learn.microsoft.com/en-us/dotnet/core/install/macos
- .NET 8 SDK download: https://dotnet.microsoft.com/en-us/download/dotnet/8.0
- Homebrew `godot-mono` cask: https://formulae.brew.sh/cask/godot-mono
