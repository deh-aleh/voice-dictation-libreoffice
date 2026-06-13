# Dettatura Vocale per LibreOffice Writer (Vosk · Offline · IT/EN)

Estensione `.oxt` per **LibreOffice Writer** che aggiunge la **dettatura vocale in
tempo reale**, interamente **offline**, tramite il motore
[Vosk](https://alphacephei.com/vosk/).

Premi un pulsante in toolbar → parla → il testo riconosciuto compare alla
posizione del cursore. Nessun dato lascia il tuo computer.

Disponibile in **Italiano** ed **Inglese**: si pubblica un `.oxt` per lingua e per
piattaforma (le due lingue possono anche coesistere installate insieme).

---

## Caratteristiche

- 🔒 **100% offline** — privacy totale, nessuna connessione richiesta.
- 🌍 **IT / EN** — modelli Vosk `small` (~50 MB), pensati per lo streaming.
- 🧩 **All-in-one** — dipendenze Python e modello bundlati nell'`.oxt`, caricati
  dal Python interno di LibreOffice (nessun `pip` lato utente).
- 🐍 **Robusto sulle versioni Python** — un `_cffi_backend` per ogni minor 3.9–3.14:
  lo stesso oxt gira su LibreOffice con Python diversi (vedi
  [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md) §3).
- 🖱️ **Un pulsante** in toolbar: *Inizia/Ferma Dettatura* (icona microfono che
  cambia colore: verde = pronto, rosso = in ascolto; badge lingua `it`/`en`).
- 🔘 **Due toggle** in toolbar (e nel menu): *Numeri on/off* e *Punteggiatura
  on/off*, indipendenti, stato persistito (icona blu = attivo, grigia barrata =
  disattivo). Disattivando un toggle le relative parole-comando restano testo.
- ✍️ **Punteggiatura a voce** — *"punto"* → `.`, *"virgola"* → `,`, *"nuovo
  paragrafo"* → a capo doppio, *"apri parentesi"* → `(`, ecc. (vedi tabella sotto).
- 🔢 **Numeri in cifre** — *"venti tre"* → `23`, *"duemila cinquecento"* → `2500`.
- 🔁 **Coesistenza it/en** con mutua esclusione: non ascoltano il microfono insieme.
- ⚡ **UI non bloccante** — l'audio gira in un thread separato.

---

## Struttura del progetto

```
dettatura-vocale-libreoffice/
├── README.md
├── LICENSE                     # MIT
├── Makefile                    # build locale: make all LANG=it PLATFORM=linux_x86_64
├── .github/workflows/
│   └── release.yml             # CI: matrice 3 OS × 2 lingue -> 6 oxt su tag v*
├── docs/
│   ├── ARCHITETTURA.md         # come LO carica librerie native dall'oxt
│   ├── STATO_PROGETTO.md       # a che punto siamo / roadmap
│   └── STORICO.md              # cosa fa il programma, passo per passo
├── scripts/
│   ├── fetch_deps.sh <plat>    # deps native + _cffi_backend 3.9-3.14 -> build/deps/
│   ├── fetch_model.sh <lang>   # scarica il modello Vosk -> build/models/<lang>/
│   ├── build_oxt.sh <lang> <plat>  # staging + zip -> dist/voice-dictation-<lang>-<plat>.oxt
│   └── _pack.py                # sostituzioni (coesistenza/token) + zip portabile
├── build/                      # [build] deps, modelli, staging (non versionato)
├── dist/                       # [build] gli .oxt prodotti (non versionato)
└── src/                        # <-- diventa la RADICE dell'archivio .oxt
    ├── description.xml         # metadati estensione (@PLATFORM@, @MODEL_LANG_*@)
    ├── Addons.xcu              # pulsante in toolbar (interruttore unico)
    ├── ProtocolHandler.xcu     # instrada il click -> componente Python
    ├── dettatura.py            # componente UNO + motore Vosk + lockfile
    ├── trasformazione.py       # post-elaborazione: punteggiatura + numeri
    ├── META-INF/manifest.xml   # registra componente e .xcu
    ├── descriptions/           # testi mostrati nel Gestore Estensioni
    └── icons/                  # mic_*_{16,26}.png (varianti _it/_eng) + extension_icon.png
```

`build/` e `dist/` si rigenerano e **non** sono versionati (`.gitignore`).

---

## Build

Prerequisiti: `bash`, `python3` + `pip`, `curl`. (Niente `zip`/`unzip`: lo zip lo
fa Python, per portabilità su Windows/macOS.)

### Locale (una combinazione lingua/piattaforma)

```bash
make all LANG=it PLATFORM=linux_x86_64   # -> dist/voice-dictation-it-linux_x86_64.oxt
make oxt LANG=en                         # riusa deps/model già scaricati
```

Variabili: `LANG=it|en` (default `it`), `PLATFORM=linux_x86_64|windows_x86_64|macos_aarch64`
(default `linux_x86_64`).

### Tutte le piattaforme (release, via GitHub Actions)

Le wheel native vanno costruite **su ciascun OS**: impossibile da una sola
macchina. Ci pensa la CI. Basta un tag:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

Il workflow builda su `ubuntu`/`windows`/`macos`, per `it` ed `en`, e allega le
**6 oxt** a una GitHub Release.

---

## Installazione (utente finale)

1. Scarica l'`.oxt` della tua lingua/piattaforma (es. `voice-dictation-it-linux_x86_64.oxt`).
2. LibreOffice → **Strumenti → Gestione estensioni → Aggiungi…** → seleziona l'`.oxt`.
3. Riavvia LibreOffice.
4. Apri Writer: comparirà il pulsante **Inizia/Ferma Dettatura** in toolbar.

Puoi installare IT ed EN insieme: avrai due pulsanti, ma uno solo può ascoltare
alla volta.

---

## Uso

1. Posiziona il cursore dove vuoi scrivere.
2. Clicca **Inizia Dettatura** e parla.
3. Il testo appare in tempo reale.
4. Clicca di nuovo per fermare.

### Punteggiatura a voce

Le parole-comando vengono convertite nel carattere corrispondente, con la
spaziatura corretta (niente spazio prima di `.` o `)`, ecc.). Ogni `.oxt` usa la
tabella della sua lingua (selezionata a build-time, vedi nota sotto):

| Output | Italiano | English |
|---|---|---|
| `.` | punto | period · full stop |
| `,` | virgola | comma |
| `;` | punto e virgola | semicolon |
| `:` | due punti | colon |
| `?` | punto interrogativo | question mark |
| `!` | punto esclamativo | exclamation mark · exclamation point |
| a capo | nuova linea | new line |
| a capo doppio | nuovo paragrafo | new paragraph |
| `(` | apri parentesi | open paren · open parenthesis |
| `)` | chiudi parentesi | close paren · close parenthesis |
| `"` | apri/chiudi virgolette | open/close quote(s) |
| `-` | trattino | hyphen |
| `—` | lineetta | dash · em dash |
| `*` | asterisco | asterisk |
| `/` | barra | slash |

### Numeri

I numeri dettati a voce diventano cifre: *"venti tre"* → `23`,
*"duecentotrenta"* → `230`, *"tremila cinquecento"* → `3500`,
*"due milioni trecento mila"* → `2300000` (in inglese: *"twenty three"* → `23`,
*"two thousand five hundred"* → `2500`). Funziona sia con i token separati sia con
le forme concatenate.

Due numeri **indipendenti** restano separati: *"venti tre cinquanta quattro"* →
`23 54` (**non** `77`).

> Mappatura e logica in [`src/trasformazione.py`](src/trasformazione.py). La lingua
> e' iniettata a build-time: `scripts/_pack.py` sostituisce il token `@LANG@` con
> `it`/`en`, cosi' lo stesso modulo serve entrambe le distribuzioni.

---

## Come funziona (in breve)

```
[Click pulsante] --Addons.xcu--> URL "vnd.libreitalia.dettatura.<lang>:toggle"
       --ProtocolHandler.xcu--> DettaturaHandler.dispatch() (dettatura.py)
       --> lockfile: una sola lingua/finestra ascolta alla volta
       --> thread audio: sounddevice -> Vosk -> testo grezzo
       --> trasformazione.py: punteggiatura + numeri -> testo finale
       --> UNO: insertString(view_cursor, testo)
```

Dettaglio tecnico completo: [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).
Cosa fa il programma passo per passo: [docs/STORICO.md](docs/STORICO.md).

---

## Non scrive? Risoluzione problemi

Writer → menu **Dettatura: log → Apri cartella dei log**: si apre la cartella
condivisa `voice-dictation-logs/`, con un file per lingua (`voice_dictation_it.log`,
`voice_dictation_en.log`). La voce è UNICA anche con it+en installate insieme.
Causa più comune: **microfono mutato, a volume 0, o permessi**.

- 🪟 [docs/TROUBLESHOOTING_WINDOWS.md](docs/TROUBLESHOOTING_WINDOWS.md)
- 🐧 [docs/TROUBLESHOOTING_LINUX.md](docs/TROUBLESHOOTING_LINUX.md)

---

## Licenza

[MIT](LICENSE).

Vosk è distribuito sotto licenza Apache 2.0; i modelli acustici hanno licenze
proprie (verificare sul sito Vosk prima della ridistribuzione).
