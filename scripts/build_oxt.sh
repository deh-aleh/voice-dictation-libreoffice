#!/usr/bin/env bash
# build_oxt.sh <lang> <platform>
#
# Assembla l'.oxt per una combinazione (lingua, piattaforma):
#   1. copia src/ in una cartella di staging (senza pythonpath/ e model/);
#   2. inietta le deps native (build/deps) e il modello giusto (build/models/<lang>);
#   3. applica sostituzioni (coesistenza it/en + token) e zippa via _pack.py.
#
# Richiede che prima siano stati eseguiti fetch_deps.sh e fetch_model.sh <lang>.
#
#   <lang>     = it | en
#   <platform> = linux_x86_64 | windows_x86_64 | macos_aarch64
set -euo pipefail

LANG_CODE="${1:?uso: build_oxt.sh <it|en> <platform>}"
PLATFORM="${2:?uso: build_oxt.sh <it|en> <platform>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYBIN="${PYTHON:-python3}"

SRC="$ROOT/src"
DEPS="$ROOT/build/deps"
MODEL="$ROOT/build/models/$LANG_CODE"
STAGE="$ROOT/build/stage/${LANG_CODE}-${PLATFORM}"
OUT="$ROOT/dist/voice-dictation-${LANG_CODE}-${PLATFORM}.oxt"

# Nome lingua del modello (per display-name in description.xml).
case "$LANG_CODE" in
  it) ML_IT="Italiano"; ML_EN="Italian" ;;
  en) ML_IT="Inglese";  ML_EN="English" ;;
  *) echo "Lingua sconosciuta: $LANG_CODE" >&2; exit 1 ;;
esac

# Token <platform> di LibreOffice (description.xml).
case "$PLATFORM" in
  linux_x86_64)   LO_PLATFORM="linux_x86_64" ;;
  windows_x86_64) LO_PLATFORM="windows_x86_64" ;;
  macos_aarch64)  LO_PLATFORM="macosx_aarch64" ;;
  *) echo "Piattaforma sconosciuta: $PLATFORM" >&2; exit 1 ;;
esac

[ -d "$DEPS" ]  || { echo "Manca build/deps: esegui fetch_deps.sh $PLATFORM" >&2; exit 1; }
[ -d "$MODEL" ] || { echo "Manca $MODEL: esegui fetch_model.sh $LANG_CODE" >&2; exit 1; }

echo ">> Staging in $STAGE"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -a "$SRC"/. "$STAGE"/
# src/ puo' contenere pythonpath/model locali: li ripulisco e reinietto puliti.
rm -rf "$STAGE/pythonpath" "$STAGE/model"
mkdir -p "$STAGE/pythonpath" "$STAGE/model"
cp -a "$DEPS"/.  "$STAGE/pythonpath"/
cp -a "$MODEL"/. "$STAGE/model"/

echo ">> Sostituzioni (lang=$LANG_CODE, platform=$LO_PLATFORM) + zip"
"$PYBIN" "$ROOT/scripts/_pack.py" \
    --stage "$STAGE" --out "$OUT" \
    --lang "$LANG_CODE" --lo-platform "$LO_PLATFORM" \
    --model-lang-it "$ML_IT" --model-lang-en "$ML_EN"

echo ">> Installa con: Strumenti > Gestione estensioni > Aggiungi"
