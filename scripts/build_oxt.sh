#!/usr/bin/env bash
# Comprime il contenuto di src/ in dist/dettatura-vocale.oxt.
# Un .oxt e' un semplice archivio ZIP: la radice dello ZIP deve contenere
# direttamente description.xml e META-INF/ (NON la cartella src/).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src"
DIST="$ROOT/dist"
OUT="$DIST/dettatura-vocale.oxt"

mkdir -p "$DIST"
rm -f "$OUT"

echo ">> Creo $OUT"
( cd "$SRC" && zip -r -X "$OUT" . \
    -x '*.DS_Store' -x '__pycache__/*' -x '*/__pycache__/*' -x '*.pyc' )

echo ">> Pacchetto pronto: $OUT"
echo "   Installa con: Strumenti > Gestione estensioni > Aggiungi"
