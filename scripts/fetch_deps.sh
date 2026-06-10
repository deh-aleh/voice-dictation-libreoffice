#!/usr/bin/env bash
# Installa le dipendenze Python dentro src/pythonpath/ cosi' che vengano bundlate nell'oxt.
#
# IMPORTANTE (binari nativi):
#   vosk e sounddevice contengono codice compilato (libvosk, PortAudio/CFFI).
#   Le ruote scaricate qui valgono SOLO per l'OS/architettura di chi esegue lo script.
#   Per un .oxt davvero multipiattaforma vanno installate le wheel di ogni piattaforma
#   target (vedi docs/ARCHITETTURA.md, sezione "multipiattaforma").
#
# Usa il Python di sistema. Per la massima compatibilita' con il Python interno di
# LibreOffice, eseguire idealmente con una versione di Python vicina a quella di LO.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/src/pythonpath"
PYBIN="${PYTHON:-python3}"

echo ">> Installo vosk + sounddevice in $DEST"
mkdir -p "$DEST"

"$PYBIN" -m pip install \
    --target "$DEST" \
    --upgrade \
    vosk sounddevice

echo ">> Fatto. Verifica che i .so/.dll nativi siano presenti in $DEST"
