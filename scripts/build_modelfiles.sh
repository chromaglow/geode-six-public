#!/bin/bash
# Build Ollama modelfiles for Geode Six
# Run from the geode-six root directory

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELFILE_DIR="$SCRIPT_DIR/../modelfiles"

echo "=== Building Geode Six Modelfiles ==="

echo "[1/4] Building geode-llama31..."
ollama create geode-llama31 -f "$MODELFILE_DIR/Modelfile.llama31"

echo "[2/4] Building geode-dolphin..."
ollama create geode-dolphin -f "$MODELFILE_DIR/Modelfile.dolphin"

echo "[3/4] Building geode-biomistral..."
ollama create geode-biomistral -f "$MODELFILE_DIR/Modelfile.biomistral"

echo "[4/4] Building geode-llava..."
ollama create geode-llava -f "$MODELFILE_DIR/Modelfile.llava"

echo ""
echo "=== All modelfiles built successfully ==="
echo "Available models:"
ollama list | grep geode
