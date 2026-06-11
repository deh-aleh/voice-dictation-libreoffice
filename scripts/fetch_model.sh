#!/usr/bin/env bash
# fetch_model.sh <lang>
#
# Scarica il modello Vosk "small" della lingua scelta in build/models/<lang>/.
# Il modello e' SOLO dati (nessun vincolo di OS/Python): la stessa cartella vale
# per ogni piattaforma. Lo teniamo separato per lingua perche' ogni oxt ne bundla
# uno solo (it OPPURE en).
#
#   <lang> = it | en
set -euo pipefail

LANG_CODE="${1:?uso: fetch_model.sh <it|en>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYBIN="${PYTHON:-python3}"

# Modelli "small" (~50 MB), adatti allo streaming in tempo reale.
case "$LANG_CODE" in
  it) MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip" ;;
  en) MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" ;;
  *) echo "Lingua sconosciuta: $LANG_CODE (attese: it, en)" >&2; exit 1 ;;
esac

DEST="$ROOT/build/models/$LANG_CODE"
TMP="$(mktemp -d)"

echo ">> Scarico modello Vosk ($LANG_CODE): $MODEL_URL"
curl -L "$MODEL_URL" -o "$TMP/model.zip"

echo ">> Estraggo in $DEST"
# Estrazione via python (portabile: niente unzip su Windows/macOS runner).
"$PYBIN" - "$TMP/model.zip" "$TMP/out" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY

# Lo zip contiene una cartella tipo vosk-model-small-it-0.22/: ne prendo il contenuto.
SUBDIR="$(find "$TMP/out" -maxdepth 1 -type d -name 'vosk-model-*' | head -n1)"
rm -rf "$DEST"; mkdir -p "$DEST"
cp -a "$SUBDIR"/. "$DEST"/

rm -rf "$TMP"
echo ">> Modello pronto in: $DEST"
