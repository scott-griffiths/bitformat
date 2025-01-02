#!/bin/bash
set -e  # Exit on any error

# Function to log steps
log() {
    echo "==> $1"
}

# Create and activate virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    log "Creating uv virtual environment"
    uv venv
fi

log "Activating virtual environment"
source .venv/bin/activate

# Install dependencies including dev dependencies
log "Installing dependencies"
uv pip install -r pyproject.toml -r dev-requirements.txt

# Build Rust components
log "Building Rust components"
(cd bit_rust && uvx maturin develop --release --uv)

# Run tests
log "Running tests"
uv run pytest --benchmark-skip