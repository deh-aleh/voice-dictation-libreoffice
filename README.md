# Dettatura Vocale per LibreOffice Writer (Vosk · Italiano · Offline)

Estensione `.oxt` per **LibreOffice Writer** che aggiunge la **dettatura vocale in
tempo reale**, interamente **offline**, in **lingua italiana**, tramite il motore
[Vosk](https://alphacephei.com/vosk/).

Premi un pulsante in toolbar → parla → il testo riconosciuto compare alla
posizione del cursore. Nessun dato lascia il tuo computer.

> ⚠️ **Stato: prototipo / scaffold iniziale (v0.1.0).** Lo scheletro completo
> (configurazione UNO + componente Python) è pronto. Il bundling dei binari nativi
> multipiattaforma è la parte ancora aperta — vedi
> [docs/STATO_PROGETTO.md](docs/STATO_PROGETTO.md).

---

## Caratteristiche

- 🔒 **100% offline** — privacy totale, nessuna connessione richiesta.
- 🇮🇹 **Italiano** — modello acustico Vosk `small-it` (~50 MB), pensato per lo streaming.
- 🧩 **Architettura "all-in-one"** — dipendenze Python e modello bundlati nell'`.oxt`,
  caricati dal Python interno di LibreOffice (nessun `pip` lato utente).
- 🖱️ **Un pulsante** in toolbar: *Inizia/Ferma Dettatura*.
- ⚡ **UI non bloccante** — l'audio gira in un thread separato.
- ✍️ **Inserimento al cursore** tramite API UNO (view-cursor di Writer).

---

## Struttura del progetto

```
dettatura-vocale-libreoffice/
├── README.md
├── LICENSE                     # MIT
├── Makefile                    # make deps | model | oxt | all | clean
├── .gitignore
├── docs/
│   ├── ARCHITETTURA.md         # come LO carica librerie native dall'oxt
│   └── STATO_PROGETTO.md       # a che punto siamo / roadmap
├── scripts/
│   ├── fetch_deps.sh           # pip install --target src/pythonpath
│   ├── fetch_model.sh          # scarica il modello Vosk IT in src/model
│   └── build_oxt.sh            # zippa src/ -> dist/dettatura-vocale.oxt
└── src/                        # <-- diventa la RADICE dell'archivio .oxt
    ├── description.xml         # metadati estensione
    ├── Addons.xcu              # pulsante in toolbar
    ├── ProtocolHandler.xcu     # instrada il click -> componente Python
    ├── dettatura.py            # componente UNO + motore Vosk
    ├── META-INF/
    │   └── manifest.xml        # registra componente e .xcu
    ├── descriptions/           # testi mostrati nel Gestore Estensioni
    ├── icons/                  # mic_16.png, mic_26.png, extension_icon.png
    ├── pythonpath/             # [build] vosk, sounddevice, ... (auto su sys.path)
    └── model/                  # [build] modello acustico Vosk italiano
```

`pythonpath/` e `model/` sono popolati in fase di build e **non** versionati
(`.gitignore`): si rigenerano con `make deps` e `make model`.

---

## Build

Prerequisiti: `bash`, `python3` + `pip`, `curl`, `unzip`, `zip`.

```bash
# 1. dipendenze Python -> src/pythonpath/
make deps

# 2. modello Vosk italiano -> src/model/
make model

# 3. pacchetto installabile -> dist/dettatura-vocale.oxt
make oxt

# (oppure tutto in una volta)
make all
```

> ⚠️ `make deps` scarica wheel native (vosk, PortAudio via sounddevice) **valide
> solo per l'OS/architettura su cui lo esegui**. Per un `.oxt` multipiattaforma
> vedi [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

---

## Installazione (utente finale)

1. Scarica `dettatura-vocale.oxt`.
2. LibreOffice → **Strumenti → Gestione estensioni → Aggiungi…** → seleziona l'`.oxt`.
3. Riavvia LibreOffice.
4. Apri Writer: comparirà il pulsante **Inizia/Ferma Dettatura** in toolbar.

---

## Uso

1. Posiziona il cursore dove vuoi scrivere.
2. Clicca **Inizia Dettatura** e parla in italiano.
3. Il testo appare in tempo reale.
4. Clicca di nuovo per fermare.

---

## Come funziona (in breve)

```
[Click pulsante] --Addons.xcu--> URL "vnd.libreitalia.dettatura:toggle"
       --ProtocolHandler.xcu--> DettaturaHandler.dispatch() (dettatura.py)
       --> thread audio: sounddevice -> Vosk -> testo
       --> UNO: insertString(view_cursor, testo)
```

Dettaglio tecnico completo del caricamento dei binari nativi dall'`.oxt`:
[docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

---

## Licenza

[MIT](LICENSE).

Vosk è distribuito sotto licenza Apache 2.0; i modelli acustici hanno licenze
proprie (verificare sul sito Vosk prima della ridistribuzione).
