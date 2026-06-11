# Storico — i passaggi del programma

Documento divulgativo: ripercorre **passo per passo** cosa succede, sia in fase di
**build** (come nasce un `.oxt`) sia a **runtime** (cosa accade dal click al testo).
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
   → Risultato: un `_cffi_backend` per ogni versione di Python che LibreOffice
   potrebbe usare.

### Passo 2 — `fetch_model.sh <lang>` → `build/models/<lang>/`
1. Mappa la lingua all'URL del modello Vosk (`it` → small-it, `en` → small-en-us).
2. Scarica lo zip (~50 MB), lo estrae, sposta il contenuto della sottocartella
   `vosk-model-*` in `build/models/<lang>/`. Il modello è solo **dati**: vale per
   ogni piattaforma.

### Passo 3 — `build_oxt.sh <lang> <platform>` → `dist/voice-dictation-<lang>-<platform>.oxt`
1. **Staging**: copia `src/` in `build/stage/<lang>-<platform>/` (senza
   `pythonpath/`/`model/`), così i sorgenti restano puliti.
2. **Iniezione**: copia `build/deps/` → `stage/pythonpath/` e
   `build/models/<lang>/` → `stage/model/`.
3. **Sostituzioni** (`_pack.py`): nei file testuali (`.xml/.xcu/.py`)
   - `org.libreitalia.dettaturavocale` → `…dettaturavocale.<lang>`
   - `vnd.libreitalia.dettatura:` → `vnd.libreitalia.dettatura.<lang>:`
   - `@PLATFORM@`, `@MODEL_LANG_IT@`, `@MODEL_LANG_EN@` → valori della build.
4. **Zip**: comprime il contenuto di `stage/` (radice = `description.xml` +
   `META-INF/` + …) in un `.oxt`, escludendo cache/`.pyc`.

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
(pulsante toolbar). Importando `dettatura.py`, la riga ~41 mette `pythonpath/` in
testa a `sys.path` (le librerie bundlate vincono su quelle di sistema).

### Passo 2 — Il click
L'utente clicca il pulsante. `Addons.xcu` emette l'URL
`vnd.libreitalia.dettatura.<lang>:toggle`. `ProtocolHandler.xcu` instrada quel
protocollo a `DettaturaHandler`, di cui viene chiamato `dispatch()` → `_toggle()`.

### Passo 3 — START (mutua esclusione)
Se non si sta già ascoltando:
1. `_acquisisci_lock()` controlla `<tmp>/voice-dictation.lock`. Se un'istanza
   **viva** (anche l'altra lingua) lo detiene → rifiuta con un avviso e si ferma.
2. Altrimenti scrive il lock (PID + identifier) e avvia il motore.

### Passo 4 — Ascolto e riconoscimento (thread separato)
1. `MotoreDettatura` apre uno stream audio mono 16 kHz con `sounddevice`.
2. I blocchi audio entrano in una coda; `vosk.KaldiRecognizer` li riconosce in
   streaming, emettendo testo parziale/finale.
3. La UI resta reattiva perché tutto gira in un `threading.Thread` daemon.

### Passo 5 — Inserimento nel documento
Il testo riconosciuto viene inserito alla posizione del cursore via UNO:
`doc.getText().insertString(view_cursor, testo, False)`.

### Passo 6 — STOP
Nuovo click → `_toggle()` ferma il motore e chiama `_rilascia_lock()` (rimuove il
lock solo se è suo). Se il motore termina da solo (es. errore/device assente),
`_on_motore_stop()` rilascia comunque il lock e riporta il pulsante a "non attivo".

---

## Parte C — I tre nodi risolti

1. **Mismatch versione Python** (LibreOffice usa 3.10? 3.14?): nello stack solo
   `cffi` è legato alla minor. Si bundla un `_cffi_backend` per ogni minor 3.9–3.14
   e Python carica da solo quello giusto (il nome del file contiene la versione).

2. **Binari per OS**: un `.oxt` vale per un OS/arch. La CI con matrice di runner
   costruisce le wheel native su ciascun OS — impossibile da una sola macchina.

3. **Coesistenza it/en**: iniettando il codice lingua nei prefissi del registro,
   le due estensioni hanno identificatori distinti e convivono installate; un
   lockfile condiviso garantisce che non ascoltino il microfono nello stesso momento.
