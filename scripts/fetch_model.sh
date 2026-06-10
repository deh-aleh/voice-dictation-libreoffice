#!/usr/bin/env bash
# Scarica il modello Vosk italiano "small" (~50 MB) e ne mette il CONTENUTO in src/model/.
# Il modello small e' adatto allo streaming in tempo reale. Per maggiore accuratezza
# esiste il modello grande (~1.2 GB): cambiare MODEL_URL.
set -euo pipefail

MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/src/model"
TMP="$(mktemp -d)"

echo ">> Scarico il modello Vosk italiano..."
curl -L "$MODEL_URL" -o "$TMP/model.zip"

echo ">> Estraggo..."
unzip -q "$TMP/model.zip" -d "$TMP"

# Lo zip contiene una cartella tipo vosk-model-small-it-0.22/: ne spostiamo il contenuto.
SUBDIR="$(find "$TMP" -maxdepth 1 -type d -name 'vosk-model-*' | head -n1)"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -a "$SUBDIR"/. "$DEST"/

rm -rf "$TMP"
echo ">> Modello pronto in: $DEST"
