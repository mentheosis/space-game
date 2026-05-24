#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${ROOT_DIR}/.tools"
DOTNET_DIR="${TOOLS_DIR}/dotnet"
GODOT_DIR="${TOOLS_DIR}/godot"
DOTNET_CHANNEL="8.0"
GODOT_VERSION="4.6.3-stable"
GODOT_ZIP="Godot_v${GODOT_VERSION}_mono_macos.universal.zip"
GODOT_URL="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/${GODOT_ZIP}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This setup script is for macOS only."
  exit 1
fi

mkdir -p "${TOOLS_DIR}" "${DOTNET_DIR}" "${GODOT_DIR}"

arch="$(uname -m)"
case "${arch}" in
  arm64) dotnet_arch="arm64" ;;
  x86_64) dotnet_arch="x64" ;;
  *)
    echo "Unsupported macOS architecture: ${arch}"
    exit 1
    ;;
esac

echo "Installing .NET ${DOTNET_CHANNEL} SDK into ${DOTNET_DIR}"
curl -fsSL "https://dot.net/v1/dotnet-install.sh" -o "${TOOLS_DIR}/dotnet-install.sh"
bash "${TOOLS_DIR}/dotnet-install.sh" \
  --channel "${DOTNET_CHANNEL}" \
  --architecture "${dotnet_arch}" \
  --install-dir "${DOTNET_DIR}"

echo "Downloading Godot ${GODOT_VERSION} .NET for macOS"
curl -fL "${GODOT_URL}" -o "${TOOLS_DIR}/${GODOT_ZIP}"

echo "Extracting Godot into ${GODOT_DIR}"
rm -rf "${GODOT_DIR:?}/"*
/usr/bin/ditto -x -k "${TOOLS_DIR}/${GODOT_ZIP}" "${GODOT_DIR}"

godot_app="$(find "${GODOT_DIR}" -maxdepth 3 -name "*.app" -type d | head -n 1)"
if [[ -z "${godot_app}" ]]; then
  echo "Godot app was not found after extraction."
  exit 1
fi

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "${godot_app}" 2>/dev/null || true
fi

godot_executable_name="Godot"
if [[ -x /usr/libexec/PlistBuddy && -f "${godot_app}/Contents/Info.plist" ]]; then
  godot_executable_name="$(/usr/libexec/PlistBuddy -c "Print :CFBundleExecutable" "${godot_app}/Contents/Info.plist" 2>/dev/null || echo "Godot")"
fi
godot_bin="${godot_app}/Contents/MacOS/${godot_executable_name}"
if [[ ! -x "${godot_bin}" ]]; then
  echo "Godot executable was not found at ${godot_bin}"
  exit 1
fi

cat > "${TOOLS_DIR}/env.sh" <<EOF
#!/usr/bin/env bash
export DOTNET_ROOT="${DOTNET_DIR}"
export PATH="${DOTNET_DIR}:\$PATH"
export GODOT_BIN="${godot_bin}"
EOF

chmod +x "${TOOLS_DIR}/env.sh"

echo
echo "Setup complete."
echo "Run this before validation or development shell commands:"
echo "  source .tools/env.sh"
echo
echo "Installed Godot:"
echo "  ${godot_app}"
echo
"${DOTNET_DIR}/dotnet" --info | sed -n '1,12p'
