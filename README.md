# Dettatura Vocale per LibreOffice Writer

🇬🇧 [Read in English](README_EN.md)

---

## Perché l'ho ideata

Ci sono tante persone che non riescono a usare la tastiera come la usiamo noi: magari hanno una disabilità, magari le mani fanno male, magari sono cresciute prima che i computer esistessero e una tastiera è ancora qualcosa di estraneo, o semplicemente vanno di fretta.

Ci sono anche persone che hanno avuto un incidente, o una malattia, e scrivere è diventato doloroso o impossibile.

Volevo dare a queste persone un modo per **parlare** e vedere le parole apparire sullo schermo. Senza configurazioni complicate, senza abbonamenti, senza mandare la propria voce ai server di qualche azienda dall'altra parte del mondo.

Questa estensione ti permette di parlare direttamente dentro LibreOffice Writer. Premi un pulsante, parli, il testo appare. Fine.

E la parte migliore? **Tutto rimane sul tuo computer.** La tua voce non esce mai dalla tua macchina. Non serve internet. Niente account. Niente cloud. Solo tu e il tuo microfono.

---

## Caratteristiche

- 🔒 **100% offline** — la tua voce non lascia mai il tuo computer, mai
- 🌍 **Italiano e Inglese** — un file `.oxt` separato per ogni lingua
- 🧩 **Tutto incluso** — le dipendenze Python e il modello vocale sono dentro l'`.oxt`, nessuna installazione aggiuntiva necessaria
- 🖱️ **Un pulsante** — clicca per iniziare, clicca per fermare; l'icona del microfono diventa rossa quando ascolta
- ✍️ **Punteggiatura a voce** — dici *"punto"* → `.`, *"virgola"* → `,`, *"nuovo paragrafo"* → doppio a capo, e molto altro
- 🔢 **Numeri in cifre** — dici *"venti tre"* → `23`, *"duemila cinquecento"* → `2500`
- 🎛️ **Comandi a voce** — grassetto, corsivo, sottolineato, liste, allineamento, dimensione font, stampa, annulla/rifai — tutto con la voce, senza toccare il mouse
- 🔘 **Toggle indipendenti** — puoi attivare o disattivare numeri, punteggiatura e comandi di formattazione separatamente
- 🛠️ **Dizionari editabili** — puoi rinominare qualsiasi comando o frase di punteggiatura dal file di config
- 🔁 **Italiano + Inglese possono coesistere** — installa entrambi, ma solo uno ascolta alla volta
- ⚡ **Non blocca LibreOffice** — l'audio gira in un thread separato, LibreOffice rimane reattivo

---

## Installazione (utente finale)

1. Vai nella [pagina delle Release](../../releases) e scarica il file `.oxt` per la tua lingua e piattaforma, esempio `voice-dictation-[LINGUA]-[PIATTAFORMA].oxt`.
2. Apri LibreOffice → **Strumenti → Gestione estensioni → Aggiungi…** → seleziona il file `.oxt`.
3. Riavvia LibreOffice.
4. Apri Writer: comparirà il pulsante **Inizia/Ferma Dettatura** nella barra degli strumenti.

Puoi installare la versione italiana e quella inglese insieme. Avrai due pulsanti, ma uno solo può ascoltare alla volta.

---

## Come si usa

1. Clicca nel documento dove vuoi scrivere.
2. Clicca **Inizia Dettatura** e inizia a parlare.
3. Il testo appare in tempo reale mentre parli.
4. Clicca di nuovo per fermare.

---

## Punteggiatura a voce

Dici queste parole e vengono convertite nel simbolo corrispondente, con la spaziatura corretta (niente spazio prima di `.` o `)`, ecc.).

Puoi modificare la lista completa nel file di config (`punteggiatura_map`).

| Output | Frase in italiano |
|---|---|
| `.` | punto |
| `,` | virgola |
| `;` | punto e virgola |
| `:` | due punti |
| `?` | punto interrogativo |
| `!` | punto esclamativo |
| a capo | a capo |
| doppio a capo | nuovo paragrafo |
| `(` | apri parentesi |
| `)` | chiudi parentesi |
| `"` | apri/chiudi virgolette |
| `-` | trattino |
| `—` | lineetta |
| `*` | asterisco |
| `/` | barra |
| `@` | chiocciola |
| `$` | dollari |
| `€` | euro |
| `£` | sterline |
| `%` | percentuale |
| `#` | hashtag |
| `...` | puntini di sospensione |
| `etc. etc.` | eccetera |

---

## Numeri a voce

I numeri dettati a voce diventano cifre: *"venti tre"* → `23`, *"duecentotrenta"* → `230`, *"tremila cinquecento"* → `3500`, *"due milioni trecento mila"* → `2300000`. Funziona sia con i token separati che con le forme concatenate.

Due numeri **indipendenti** restano separati: *"venti tre cinquanta quattro"* → `23 54` (**non** `77`).

---

## Comandi di formattazione a voce

Dici queste frasi mentre detti — scatenano un'azione invece di essere scritte. Comandi e testo normale si possono mescolare nella stessa frase, ad esempio *"attiva grassetto questo è importante disattiva grassetto"*.

Puoi attivare o disattivare tutti i comandi con il toggle **Comandi formattazione** nel menu Dettatura. Quando sono off, queste frasi vengono scritte come testo normale.

La lista completa è editabile nel file di config (`comandi_map`).

| Azione | Frase in italiano |
|---|---|
| Lista puntata on/off | elenco puntato |
| Lista numerata on/off | elenco numerato |
| Fine lista | fine elenco |
| Grassetto on | attiva grassetto · tutto grassetto |
| Grassetto off | disattiva grassetto · fine grassetto |
| Corsivo on | attiva corsivo · tutto corsivo |
| Corsivo off | disattiva corsivo · fine corsivo |
| Sottolineato on | attiva sottolineato |
| Sottolineato off | disattiva sottolineato |
| Maiuscola sulla prossima parola | maiuscolo |
| MAIUSCOLO continuo on | tutto maiuscolo |
| MAIUSCOLO continuo off | fine maiuscolo |
| Annulla ultimo blocco | cancella ultimo |
| Rifai (redo) | rifai · ripristina |
| Azzera formattazione | testo normale |
| Interruzione di pagina | interruzione pagina · salto pagina |
| Allinea a sinistra | allinea sinistra |
| Allinea al centro | allinea centro |
| Allinea a destra | allinea destra |
| Giustifica | giustifica · giustificato |
| Stampa (apre dialogo) | stampa |
| Ingrandisci font (di N, default 4) | aumenta font · ingrandisci font |
| Riduci font (di N, default 4) | diminuisci font · riduci font |
| Inserisci data odierna | ritorna data · inserisci data · data odierna |

Per il font puoi dire la quantità: *"aumenta font cinque"* → +5pt. Senza numero usa il passo di default (4pt).

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

---

## Struttura del progetto

```
dettatura-vocale-libreoffice/
├── README.md                       # in italiano (questo file)
├── README_EN.md                    # in inglese
├── LICENSE                         # MIT
├── Makefile                        # build locale: make all LANG=it PLATFORM=linux_x86_64
├── .github/workflows/
│   └── release.yml                 # CI: 3 OS × 2 lingue → 6 oxt su tag v*
├── docs/
│   ├── ARCHITETTURA.md             # come LibreOffice carica le librerie native dall'oxt
│   ├── STATO_PROGETTO.md           # stato attuale / roadmap
│   └── FUNZIONAMENTO.md             # flusso dalla build al testo, passo per passo
├── scripts/
│   ├── fetch_deps.sh <plat>        # dipendenze native + _cffi_backend 3.9-3.14 -> build/deps/
│   ├── fetch_model.sh <lang>       # scarica il modello Vosk -> build/models/<lang>/
│   ├── build_oxt.sh <lang> <plat>  # staging + zip -> dist/voice-dictation-<lang>-<plat>.oxt
│   └── _pack.py                    # sostituzioni token + zip portabile
├── build/                          # [generato] dipendenze, modelli, staging (non versionato)
├── dist/                           # [generato] i file .oxt prodotti (non versionato)
└── src/                            # <-- diventa la radice dell'archivio .oxt
    ├── description.xml             # metadati estensione
    ├── Addons.xcu                  # pulsante toolbar
    ├── ProtocolHandler.xcu         # instrada il click al componente Python
    ├── dettatura.py                # componente UNO + motore Vosk + lockfile
    ├── trasformazione.py           # post-elaborazione: punteggiatura + numeri
    ├── META-INF/manifest.xml
    ├── descriptions/               # testi mostrati nel Gestore Estensioni
    └── icons/                      # icone microfono (16px, 26px) + icona estensione
```

---

## Build (per sviluppatori)

Prerequisiti: `bash`, `python3` + `pip`, `curl`. Non serve `zip`/`unzip` (Python gestisce lo zip per compatibilità cross-platform).

### Build locale (una lingua/piattaforma)

```bash
make all LANG=it PLATFORM=linux_x86_64   # -> dist/voice-dictation-it-linux_x86_64.oxt
make oxt LANG=en                         # riusa dipendenze/modello già scaricati
```

Variabili: `LANG=it|en` (default `it`), `PLATFORM=linux_x86_64|windows_x86_64|macos_aarch64` (default `linux_x86_64`).

### Tutte le piattaforme (release, via GitHub Actions)

Le wheel native vanno costruite su ciascun OS — impossibile da una sola macchina. Ci pensa la CI. Basta un tag:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

Il workflow builda su `ubuntu` / `windows` / `macos`, per `it` ed `en`, e allega le **6 oxt** a una GitHub Release.

---

## Non funziona? Risoluzione problemi

I log stanno in `<tmp>/voice-dictation-logs/`, un file per lingua (`voice_dictation_it.log`, `voice_dictation_en.log`). Aprili a mano. Il file di config per lingua è lì: `voice_dictation_<lang>.cfg.json`.

Flag di config: `numeri`, `punteggiatura`, `comandi`, `verbose`, `debug`, `verbose-logging`.

Causa più comune di silenzio: **microfono mutato, volume a 0, o permessi mancanti**.

- 🪟 [Risoluzione problemi su Windows](docs/TROUBLESHOOTING_WINDOWS.md)
- 🐧 [Risoluzione problemi su Linux](docs/TROUBLESHOOTING_LINUX.md)

---

## Licenza

[MIT](LICENSE).

Vosk è distribuito sotto licenza Apache 2.0. I modelli acustici hanno licenze proprie — verifica sul sito Vosk prima della ridistribuzione.
