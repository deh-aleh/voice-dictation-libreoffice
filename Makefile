# Makefile - flusso di build dell'estensione.
#   make deps   -> installa vosk/sounddevice in src/pythonpath/
#   make model  -> scarica il modello Vosk italiano in src/model/
#   make oxt    -> crea dist/dettatura-vocale.oxt
#   make all    -> deps + model + oxt
#   make clean  -> rimuove dist/, pythonpath/, model/

.PHONY: all deps model oxt clean

all: deps model oxt

deps:
	bash scripts/fetch_deps.sh

model:
	bash scripts/fetch_model.sh

oxt:
	bash scripts/build_oxt.sh

clean:
	rm -rf dist
	find src/pythonpath -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +
	find src/model      -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +
