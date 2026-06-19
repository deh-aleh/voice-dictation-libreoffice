# Come funziona — flusso dalla build al testo

Documento divulgativo: ripercorre **passo per passo** cosa succede, sia in fase di
**build** (come nasce un `.oxt`) sia a **runtime** (dal click al testo nel documento).
Per il "perché" delle scelte tecniche vedi [ARCHITETTURA.md](ARCHITETTURA.md).

---

## Parte A — Pipeline di build (da `src/` all'`.oxt`)

Comando tipico: `make all LANG=it PLATFORM=linux_x86_64`.

### Passo 1 — `fetch_deps.sh <platform>` → `build/deps/`
1. `pip install --target build/deps sounddevice cffi vosk`: scarica nel target
   (NON nel sistema) le librerie per l'OS corrente. `sounddevice` è pure-python,
   `vosk` porta `libvosk.so`, `cffi` porta il suo `_cffi_backend` nativo.
2. Per **ogni** minor Python 3.9→3.14: `pip download cffi --abi cpXX` e si estrae
   **solo** `_cffi_backend.cpython-3XX-*.so`, affiancandolo agli altri.
   Risultato: un `_cffi_backend` per ogni versione di Python che LibreOffice
   potrebbe usare.

### Passo 2 — `fetch_model.sh <lang>` → `build/models/<lang>/`
1. Mappa la lingua all'URL del modello Vosk (`it` → small-it, `en` → small-en-us).
2. Scarica lo zip (~50 MB), lo estrae, sposta il contenuto della sottocartella
   `vosk-model-*` in `build/models/<lang>/`. Il modello è solo **dati**: vale per
   ogni piattaforma.

### Passo 3 — `build_oxt.sh <lang> <platform>` → `dist/voice-dictation-<lang>-<platform>.oxt`
1. **Staging**: copia `src/` in `build/stage/<lang>-<platform>/` (senza
   `pythonpath/`/`model/`), così i sorgenti restano puliti e versionabili.
2. **Iniezione**: copia `build/deps/` → `stage/pythonpath/` e
   `build/models/<lang>/` → `stage/model/`.
3. **Sostituzioni** (`_pack.py`): nei file testuali (`.xml/.xcu/.py`) sostituisce
   i token di lingua/piattaforma così ogni oxt ha identificatori univoci:
   - `org.libreitalia.dettaturavocale` → `…dettaturavocale.<lang>`
   - `vnd.libreitalia.dettatura:` → `vnd.libreitalia.dettatura.<lang>:`
   - `@PLATFORM@`, `@MODEL_LANG_IT@`, `@MODEL_LANG_EN@`, `@LANG@` → valori reali.
4. **Zip**: comprime il contenuto di `stage/` in un `.oxt`, escludendo cache/`.pyc`.

### Passo 4 — Release (CI, opzionale)
Su tag `v*`, `.github/workflows/release.yml` esegue i passi 1–3 su **3 OS**
(ubuntu/windows/macos) per **2 lingue**, e allega le **6 oxt** a una GitHub Release.
Le wheel native si possono produrre solo sull'OS corrispondente: per questo serve
la matrice CI.

---

## Parte B — Ciclo di vita a runtime (dal click al testo)

### Passo 1 — Caricamento dell'estensione
All'avvio, LibreOffice legge `manifest.xml` e registra:
`dettatura.py` (componente UNO), `ProtocolHandler.xcu` (routing), `Addons.xcu`
(pulsante toolbar). Importando `dettatura.py`:
- La riga ~44 mette `pythonpath/` in **testa** a `sys.path` (le librerie bundlate
  vincono su quelle di sistema).
- `trasformazione.py` viene caricato via `importlib` con nome univoco per lingua
  (es. `trasformazione_it`) per evitare collisioni tra le due estensioni it/en e
  cache obsolete dopo aggiornamenti senza riavvio completo.
- Il file di config per-lingua (`voice_dictation_<lang>.cfg.json`) viene letto;
  se assente viene creato con i valori di default.

### Passo 2 — Il click (pulsante o menu)
L'utente clicca il pulsante. `Addons.xcu` emette l'URL
`vnd.libreitalia.dettatura.<lang>:toggle`. `ProtocolHandler.xcu` instrada quel
protocollo a `DettaturaHandler`, di cui viene chiamato `dispatch()`.

`dispatch()` decodifica l'azione dalla parte dopo il protocollo:
- `toggle` → avvia/ferma la dettatura
- `togglenumbers` → attiva/disattiva riconoscimento numeri
- `togglepunct` → attiva/disattiva punteggiatura a voce
- `togglecommands` → attiva/disattiva comandi di formattazione

### Passo 3 — START (mutua esclusione + config reload)
Se non si sta già ascoltando:
1. **Config reload**: rilegge il file JSON — così le modifiche manuali a
   `comandi_map` / `punteggiatura_map` sono attive senza riavviare LibreOffice.
2. **Lock**: `_acquisisci_lock()` controlla `<tmp>/voice-dictation.lock`. Se
   un'istanza **viva** (anche l'altra lingua) lo detiene → rifiuta con un avviso.
3. Altrimenti scrive il lock (PID + identifier) e avvia `MotoreDettatura`.

### Passo 4 — Ascolto e riconoscimento (thread separato)
1. `MotoreDettatura` apre uno stream audio mono 16 kHz con `sounddevice`.
2. I blocchi audio entrano in una coda; `vosk.KaldiRecognizer` li riconosce in
   streaming, emettendo testo parziale/finale.
3. La UI resta reattiva perché tutto gira in un `threading.Thread` daemon.

### Passo 5 — Post-elaborazione (`trasformazione.py`)
Il testo grezzo Vosk passa attraverso la funzione `trasforma()` che applica,
nell'ordine, solo le trasformazioni attive (in base ai toggle):

1. **Punteggiatura**: scansiona il testo alla ricerca di frasi-comando
   (da `punteggiatura_map` nel config); le sostituisce con il simbolo corretto,
   aggiustando gli spazi prima/dopo. Esempi: *"punto"* → `.`, *"virgola"* → `,`.
2. **Numeri**: riconosce sequenze di parole-numero italiane o inglesi
   (`_costruisci_atomi` + `_combina_run`) e le converte in cifre.
   Due numeri indipendenti restano separati: *"venti tre cinquanta quattro"* → `23 54`.

### Passo 6 — Comandi di formattazione
`_segmenta_comandi()` scansiona il testo trasformato alla ricerca di frasi-comando
(da `comandi_map` nel config). Il testo viene spezzato in **segmenti**: testo
normale da inserire + comandi da eseguire, nell'ordine in cui compaiono.

Ogni comando esegue un'azione UNO:
- Grassetto/corsivo/sottolineato: `setPropertyValue` sul view cursor.
- Liste, allineamento, stampa, annulla/rifai, interruzione pagina: `dispatcher.executeDispatch()` con URL `.uno:*`.
- Font size: `setPropertyValue("CharHeight", ...)`.
- Maiuscole: stato interno, applicato alle parole successive.
- Data odierna: `datetime.date.today()` formattato e inserito come testo.

### Passo 7 — Inserimento nel documento
Il testo (o ogni segmento) viene inserito alla posizione del cursore via UNO:
```python
doc.getText().insertString(view_cursor, testo, False)
```

### Passo 8 — STOP
Nuovo click → `_toggle()` ferma il motore e chiama `_rilascia_lock()` (rimuove il
lock solo se è suo). Se il motore termina da solo (errore/device assente),
`_on_motore_stop()` rilascia il lock e riporta il pulsante a "non attivo".

---

## Parte C — I quattro nodi risolti

1. **Mismatch versione Python** (LibreOffice usa 3.10? 3.14?): nello stack solo
   `cffi` è legato alla minor. Si bundla un `_cffi_backend` per ogni minor 3.9–3.14
   e Python carica da solo quello giusto (il nome del file contiene la versione).
   Verificato su Linux con Python 3.14 (Arch Linux).

2. **Binari per OS**: un `.oxt` vale per un OS/arch. La CI con matrice di runner
   costruisce le wheel native su ciascun OS — impossibile da una sola macchina.

3. **Coesistenza it/en**: iniettando il codice lingua nei prefissi del registro,
   le due estensioni hanno identificatori distinti e convivono installate; un
   lockfile condiviso garantisce che non ascoltino il microfono nello stesso momento.

4. **Cache moduli stantia**: LibreOffice usa un singolo processo Python condiviso
   tra tutte le estensioni e tra sessioni. Un `import trasformazione` resterebbe in
   `sys.modules` dopo un aggiornamento senza riavvio completo. Soluzione:
   `importlib.util.spec_from_file_location` con nome univoco per lingua — bypassa
   la cache e carica sempre il file fisico corrente, senza collisioni tra it ed en.
