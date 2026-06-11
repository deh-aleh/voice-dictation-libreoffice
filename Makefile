# Makefile - build locale dell'estensione (una combinazione lingua/piattaforma).
# La build completa multi-OS la fa GitHub Actions (.github/workflows/release.yml).
#
#   make deps                      -> build/deps/  (vosk/sounddevice/cffi + _cffi_backend 3.9-3.14)
#   make model LANG=en             -> build/models/en/  (default LANG=it)
#   make oxt   LANG=en             -> dist/voice-dictation-en-<PLATFORM>.oxt
#   make all   LANG=it             -> deps + model + oxt
#   make clean                     -> rimuove build/ e dist/
#
# Variabili (override da riga di comando):
#   LANG=it|en              (default it)
#   PLATFORM=linux_x86_64|windows_x86_64|macos_aarch64  (default linux_x86_64)

LANG     ?= it
PLATFORM ?= linux_x86_64

.PHONY: all deps model oxt clean

all: deps model oxt

deps:
	bash scripts/fetch_deps.sh $(PLATFORM)

model:
	bash scripts/fetch_model.sh $(LANG)

oxt:
	bash scripts/build_oxt.sh $(LANG) $(PLATFORM)

clean:
	rm -rf build dist
