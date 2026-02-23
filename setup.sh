#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"
CONFIG_DST="config/config.yaml"
REQUIRED_MINOR=11
TARGET_PY="3.13"

# --- Helper: install Python via pyenv or Homebrew ---
install_python() {
    local version="$1"

    if command -v pyenv &>/dev/null; then
        echo "Installing Python $version via pyenv..."
        pyenv install -s "$version"
        pyenv local "$version"
        # Rehash so the new version is on PATH
        pyenv rehash
        PYTHON="$(pyenv which python3)"
        echo "Installed Python $version with pyenv."
        return 0
    fi

    if command -v brew &>/dev/null; then
        local brew_pkg="python@${version}"
        echo "Installing Python $version via Homebrew..."
        brew install "$brew_pkg"
        # Homebrew installs into a versioned path
        local brew_prefix
        brew_prefix="$(brew --prefix "$brew_pkg" 2>/dev/null)" || true
        if [ -n "$brew_prefix" ] && [ -x "$brew_prefix/bin/python3" ]; then
            PYTHON="$brew_prefix/bin/python3"
        else
            PYTHON="python3"
        fi
        echo "Installed Python $version with Homebrew."
        return 0
    fi

    echo "Error: Neither pyenv nor Homebrew found. Install one of them first, or install Python $version manually."
    exit 1
}

# --- Helper: find a compatible Python binary ---
find_compatible_python() {
    # Check versioned names first (most specific), then generic names, then brew paths
    local candidates=(
        "python3.13" "python3.12" "python3.11"
        "python3" "python"
    )

    # Also check Homebrew prefix paths if brew is available
    if command -v brew &>/dev/null; then
        for minor in 13 12 11; do
            local prefix
            prefix="$(brew --prefix "python@3.${minor}" 2>/dev/null)" || true
            if [ -n "$prefix" ] && [ -x "$prefix/bin/python3" ]; then
                candidates+=("$prefix/bin/python3")
            fi
        done
    fi

    for cmd in "${candidates[@]}"; do
        if command -v "$cmd" &>/dev/null || [ -x "$cmd" ]; then
            local major minor
            major=$("$cmd" -c 'import sys; print(sys.version_info.major)' 2>/dev/null) || continue
            minor=$("$cmd" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null) || continue
            if [ "$major" -eq 3 ] && [ "$minor" -ge "$REQUIRED_MINOR" ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# --- Python version check ---
echo "Checking Python version..."
PYTHON=""

if find_compatible_python; then
    PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    needs_install=false
else
    needs_install=true
    # Report what was found, if anything
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local_ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || true
            if [ -n "$local_ver" ]; then
                echo "Python 3.${REQUIRED_MINOR}+ required (found $local_ver)."
            fi
            break
        fi
    done
    if [ -z "$PYTHON" ] && [ "$needs_install" = true ] && ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
        echo "Python not found."
    fi
fi

if [ "$needs_install" = true ]; then
    echo ""
    echo "Would you like to install Python $TARGET_PY?"
    while true; do
        read -rp "Install Python $TARGET_PY? [y/n]: " yn
        case "$yn" in
            [Yy]|[Yy]es) install_python "$TARGET_PY"; break ;;
            [Nn]|[Nn]o)
                echo "Aborting setup. Install Python 3.${REQUIRED_MINOR}+ and re-run this script."
                exit 1
                ;;
            *) echo "Please enter y or n." ;;
        esac
    done
    # Re-check after install — find the newly installed binary
    if ! find_compatible_python; then
        echo "Error: Python $TARGET_PY was installed but could not be found on PATH."
        echo "Try restarting your terminal and running this script again."
        exit 1
    fi
    PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
fi

echo "Using Python $PY_VERSION ($PYTHON)"
echo ""

# --- Interactive: Install mode ---
echo "Select install mode:"
echo "  [1] Full - all features (vectors, API, tree-sitter)"
echo "  [2] Minimal - base dependencies only"
echo ""
while true; do
    read -rp "Choice [1/2]: " install_choice
    case "$install_choice" in
        1) INSTALL_MODE="full"; break ;;
        2) INSTALL_MODE="minimal"; break ;;
        *) echo "Please enter 1 or 2." ;;
    esac
done
echo ""

# --- Interactive: Platform ---
echo "Select repository source:"
echo "  [1] GitLab"
echo "  [2] GitHub"
echo "  [3] Local Directory (point at a folder of repos)"
echo ""
while true; do
    read -rp "Choice [1/2/3]: " platform_choice
    case "$platform_choice" in
        1) PLATFORM="gitlab"; break ;;
        2) PLATFORM="github"; break ;;
        3) PLATFORM="local"; break ;;
        *) echo "Please enter 1, 2, or 3." ;;
    esac
done
echo ""

# --- If local, prompt for directory path ---
if [ "$PLATFORM" = "local" ]; then
    read -rp "Path to directory containing your repos: " LOCAL_REPOS_PATH
    # Expand ~ if present
    LOCAL_REPOS_PATH="${LOCAL_REPOS_PATH/#\~/$HOME}"
    if [ ! -d "$LOCAL_REPOS_PATH" ]; then
        echo "Warning: Directory '$LOCAL_REPOS_PATH' does not exist yet. You can create it later."
    fi
    echo ""
fi

# --- Virtual environment ---
venv_python_ok() {
    # Check if existing venv has a compatible Python version
    local venv_py="$1/bin/python3"
    [ -x "$venv_py" ] || return 1
    local minor
    minor=$("$venv_py" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null) || return 1
    [ "$minor" -ge "$REQUIRED_MINOR" ]
}

if [ -n "${VIRTUAL_ENV:-}" ]; then
    if venv_python_ok "$VIRTUAL_ENV"; then
        echo "Virtual environment already active: $VIRTUAL_ENV"
    else
        echo "Active virtual environment uses an incompatible Python. Deactivate it and re-run this script."
        exit 1
    fi
elif [ -d "$VENV_DIR" ]; then
    if venv_python_ok "$VENV_DIR"; then
        echo "Activating existing virtual environment..."
        source "$VENV_DIR/bin/activate"
    else
        echo "Existing virtual environment has incompatible Python. Recreating..."
        rm -rf "$VENV_DIR"
        "$PYTHON" -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
    fi
else
    echo "Creating virtual environment in $VENV_DIR..."
    "$PYTHON" -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi

# --- Install dependencies ---
echo "Installing dependencies (mode: $INSTALL_MODE)..."
pip install --upgrade pip --quiet

if [ "$INSTALL_MODE" = "full" ]; then
    pip install -e ".[full]"
else
    pip install -e .
fi

# --- Configuration ---
CONFIG_SRC="config/${PLATFORM}.example.yaml"

if [ -f "$CONFIG_DST" ]; then
    echo "Config already exists at $CONFIG_DST, skipping."
else
    echo "Copying $PLATFORM config template to $CONFIG_DST..."
    cp "$CONFIG_SRC" "$CONFIG_DST"
    # For local platform, substitute the repos path into the config
    if [ "$PLATFORM" = "local" ] && [ -n "${LOCAL_REPOS_PATH:-}" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|/path/to/your/repos|${LOCAL_REPOS_PATH}|g" "$CONFIG_DST"
        else
            sed -i "s|/path/to/your/repos|${LOCAL_REPOS_PATH}|g" "$CONFIG_DST"
        fi
    fi
fi

# --- Working directories ---
mkdir -p repos output
echo "Working directories ready (repos/, output/)."

# --- Verify CLI entry points ---
echo ""
echo "Verifying CLI commands..."
CMDS=(sensebase sb-search sb-semantic sb-api sb-llm)
ALL_OK=true
for cmd in "${CMDS[@]}"; do
    if command -v "$cmd" &>/dev/null; then
        echo "  $cmd ... ok"
    else
        echo "  $cmd ... NOT FOUND"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo ""
    echo "Warning: Some CLI commands were not found. Try re-activating the venv:"
    echo "  source $VENV_DIR/bin/activate"
fi

# --- Done ---
echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
if [ "$PLATFORM" = "gitlab" ]; then
    echo "  1. Edit $CONFIG_DST with your GitLab URL and personal access token"
elif [ "$PLATFORM" = "github" ]; then
    echo "  1. Edit $CONFIG_DST with your GitHub personal access token"
elif [ "$PLATFORM" = "local" ]; then
    echo "  1. Verify repos_path in $CONFIG_DST points to your repos directory"
fi
echo "  2. Activate the environment:  source $VENV_DIR/bin/activate"
echo "  3. Run the pipeline:          sensebase --full"
echo ""
echo "For LLM-based extraction (optional):"
echo "  Set your Anthropic key via llm.api_key in $CONFIG_DST"
echo "  or export ANTHROPIC_API_KEY=\"sk-ant-...\""
echo "  Then run: sensebase --full --llm"
