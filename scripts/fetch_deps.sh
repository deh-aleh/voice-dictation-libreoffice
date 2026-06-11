#!/usr/bin/env bash
# fetch_deps.sh <platform>
#
# Prepara build/deps/ con le librerie Python che verranno bundlate nell'oxt
# (sottocartella pythonpath/). NON installa nulla nel sistema dell'utente:
# a runtime usa il python interno di LibreOffice, che importa da pythonpath/.
#
# Nello stack vosk+sounddevice l'UNICO pezzo legato alla versione di Python e'
# cffi (_cffi_backend). sounddevice e' pure-python; vosk e' "py3" (legato solo a
# OS/arch). Quindi per far girare lo STESSO oxt su LibreOffice con python 3.9..3.14
# basta affiancare un _cffi_backend per ogni minor: Python carica da solo quello
# che combacia col proprio interprete (il nome del file contiene la versione).
#
#   <platform> = linux_x86_64 | windows_x86_64 | macos_aarch64
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/build/deps"
PYBIN="${PYTHON:-python3}"
PLATFORM="${1:-linux_x86_64}"

CFFI_VER="2.0.0"
PY_MINORS=(3.9 3.10 3.11 3.12 3.13 3.14)

# Tag piattaforma per il download cross-versione di cffi + eventuale pin di vosk.
case "$PLATFORM" in
  linux_x86_64)   PIP_PLAT="manylinux2014_x86_64"; VOSK_SPEC="vosk" ;;
  windows_x86_64) PIP_PLAT="win_amd64";            VOSK_SPEC="vosk" ;;
  macos_aarch64)  PIP_PLAT="macosx_11_0_arm64";    VOSK_SPEC="vosk==0.3.44" ;; # 0.3.45 non ha wheel macOS; 0.3.44 = universal2
  *) echo "Piattaforma sconosciuta: $PLATFORM" >&2; exit 1 ;;
esac

echo ">> [1/2] Installo deps native della piattaforma in $DEST"
rm -rf "$DEST"; mkdir -p "$DEST"
# pip sceglie le wheel giuste per QUESTO OS: sounddevice (pure), vosk (py3/arch),
# cffi (pure-python + _cffi_backend per la minor di questo python).
"$PYBIN" -m pip install --target "$DEST" --upgrade \
    sounddevice "cffi==$CFFI_VER" "$VOSK_SPEC"

echo ">> [2/2] Affianco _cffi_backend per ogni minor 3.9-3.14 ($PLATFORM)"
TMP="$(mktemp -d)"
for PV in "${PY_MINORS[@]}"; do
    ABI="cp${PV/./}"          # 3.10 -> cp310
    OUT="$TMP/$ABI"; mkdir -p "$OUT"
    "$PYBIN" -m pip download "cffi==$CFFI_VER" \
        --no-deps --only-binary=:all: \
        --implementation cp --python-version "$PV" --abi "$ABI" \
        --platform "$PIP_PLAT" -d "$OUT" >/dev/null
    # La wheel e' uno zip: estraggo SOLO il backend nativo (portabile: niente unzip).
    "$PYBIN" - "$OUT" "$DEST" <<'PY'
import sys, glob, zipfile, os
src, dest = sys.argv[1], sys.argv[2]
whl = glob.glob(os.path.join(src, "*.whl"))[0]
with zipfile.ZipFile(whl) as z:
    for n in z.namelist():
        if os.path.basename(n).startswith("_cffi_backend.") and not n.endswith("/"):
            data = z.read(n)
            with open(os.path.join(dest, os.path.basename(n)), "wb") as f:
                f.write(data)
            print("   +", os.path.basename(n))
PY
done
rm -rf "$TMP"
echo ">> Fatto."
