# Architettura tecnica

Documento di riferimento su **come strutturare l'`.oxt` perché LibreOffice carichi
librerie esterne (vosk, sounddevice) dall'interno dell'estensione**, e sulle scelte
architetturali del progetto.

---

## 1. Anatomia di un `.oxt`

Un `.oxt` è un archivio **ZIP** con una struttura precisa alla radice:

```
(radice dello ZIP)
├── description.xml          # metadati (id, versione, piattaforme, min LO)
├── META-INF/manifest.xml    # elenca cosa registrare e con quale media-type
├── Addons.xcu               # contributo UI (pulsante toolbar)
├── ProtocolHandler.xcu      # routing protocollo -> componente
├── dettatura.py             # componente UNO Python
├── pythonpath/              # <-- librerie Python bundlate
└── model/                   # <-- dati (modello Vosk)
```

Punto chiave: la radice dell'archivio coincide con il contenuto di `src/`. Lo zip
**non** deve contenere una cartella `src/` di livello superiore.

La build non zippa `src/` direttamente: usa una **cartella di staging**
(`build/stage/<lang>-<platform>/`) dove `scripts/build_oxt.sh`:
1. copia `src/` (senza `pythonpath/`/`model/`);
2. inietta le deps native (`build/deps/`) e il modello giusto (`build/models/<lang>/`);
3. applica le sostituzioni e zippa via `scripts/_pack.py` (zip puro in Python,
   portabile su Linux/Windows/macOS senza dipendere da `zip`/`unzip`).

Così `src/` resta pulito e versionabile, e da un solo albero sorgente escono N
pacchetti (lingua × piattaforma).

---

## 2. Caricare librerie Python dall'`.oxt`: la cartella `pythonpath/`

**Meccanismo nativo di LibreOffice** (questa è la "best practice" richiesta):

> Quando LibreOffice carica un **componente Python da un'estensione**, aggiunge
> automaticamente la sottocartella `pythonpath/` di quell'estensione a
> `sys.path`.

Conseguenza pratica: qualsiasi pacchetto bundlato in `pythonpath/` diventa
importabile dal componente **senza** che l'utente installi nulla con `pip`. Le
librerie le produce `scripts/fetch_deps.sh` in `build/deps/`, e `build_oxt.sh` le
copia nello staging come `pythonpath/`:

```
pythonpath/
├── vosk/  (con libvosk.so)        # binario nativo del motore
├── sounddevice.py, _sounddevice.py
├── cffi/                          # parte pure-python di cffi (una copia)
├── _cffi_backend.cpython-39-*.so  ┐  un binario per OGNI minor Python
├── _cffi_backend.cpython-310-*.so │  (3.9–3.14): LibreOffice carica da solo
├── ...                            │  quello che combacia col suo interprete
└── _cffi_backend.cpython-314-*.so ┘  (vedi §3)
```

`dettatura.py` inserisce `pythonpath/` in **testa** a `sys.path` (riga ~41) così
il bundle self-consistent vince su eventuali pacchetti di sistema rotti.

Nel codice (`dettatura.py`) l'import è **ritardato** dentro il thread worker:

```python
from vosk import Model, KaldiRecognizer
import sounddevice as sd
```

Così, se `pythonpath/` non è ancora popolato (build incompleta), l'estensione si
carica comunque e l'errore emerge solo all'avvio della dettatura, in modo
gestito.

### Perché non usare `pip` lato utente
Il Python interno di LibreOffice spesso non espone `pip`, può essere read-only e
varia tra distribuzioni/OS. Bundlare in `pythonpath/` elimina queste variabili.

---

## 3. Il problema dei binari nativi (il vincolo reale dell'"all-in-one")

`vosk` e `sounddevice` **non sono Python puro**:

| Pacchetto     | Componente nativo                          |
|---------------|--------------------------------------------|
| `vosk`        | `libvosk.so` / `.dylib` / `.dll` (Kaldi)   |
| `sounddevice` | `cffi` + **PortAudio** (`libportaudio`)    |

Un binario compilato per Linux x86_64 **non** gira su Windows o macOS o ARM.
Quindi un `.oxt` è legato a OS/arch: serve **una release per piattaforma**.

### Strategia adottata: un `.oxt` per piattaforma, costruito in CI
GitHub Actions (`.github/workflows/release.yml`) usa una **matrice di OS**
(`ubuntu`, `windows`, `macos`): ogni runner esegue `fetch_deps.sh` con il proprio
OS e produce le wheel native di **quella** piattaforma — impossibile da una sola
macchina. `description.xml` dichiara la `<platform>` specifica (token
`linux_x86_64` / `windows_x86_64` / `macosx_aarch64`, iniettato a build-time).

Su tag `v*` la CI produce **6 oxt** (it/en × 3 OS) e le allega a una Release.

### Compatibilità versione Python — la soluzione vera
Le wheel native sono legate alla **minor di CPython** (cp39, cp310, …). Il Python
interno di LibreOffice **varia**: su Windows/macOS LO porta il suo (fisso per
versione di LO); su Linux usa quello di **sistema** (Arch oggi 3.14, Ubuntu LTS
3.10…). Non esiste UN solo target.

Analisi dello stack — solo **un** pezzo è legato alla minor:

| Pacchetto     | Tag wheel            | Legato a versione Python? |
|---------------|----------------------|---------------------------|
| `sounddevice` | `py3-none-any`       | No (pure-python)          |
| `vosk`        | `py3-none-<plat>`    | No (solo OS/arch; `libvosk` caricata via cffi) |
| `cffi`        | `cpXX-cpXX-<plat>`   | **Sì** — `_cffi_backend`  |

`cffi` **non** pubblica wheel `abi3`. Soluzione adottata: **bundlare un
`_cffi_backend` per ogni minor 3.9–3.14**. Il nome del file contiene la versione
(`_cffi_backend.cpython-312-…so`) e Python carica **solo** quello che combacia col
proprio interprete. Risultato: lo stesso oxt gira su ogni LibreOffice con Python
3.9–3.14, Arch 3.14 compreso. Lo fa `fetch_deps.sh` step [2/2] via
`pip download --abi cpXX`. (Python ≤ 3.8 resta fuori: `cffi 2.0.0` parte da cp39.)

---

## 4. Il modello Vosk: dati, non codice

Il modello (`model/`) è solo dati: nessun problema di piattaforma, ma ~50 MB
(small) o ~1.2 GB (large). Va localizzato a runtime perché il path d'installazione
dell'estensione non è noto a priori:

```python
pip = ctx.getByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
base_url  = pip.getPackageLocation("org.libreitalia.dettaturavocale")
base_path = unohelper.fileUrlToSystemPath(base_url)
model_dir = os.path.join(base_path, "model")
```

`PackageInformationProvider` è il modo corretto e portabile per trovare la cartella
della propria estensione (mai hardcodare percorsi).

---

## 5. Routing del pulsante: ProtocolHandler vs script macro

Due approcci per far reagire un pulsante:

1. **ProtocolHandler (adottato qui)** — componente UNO che implementa
   `XDispatchProvider`/`XDispatch`. Pulito, idiomatico, niente percorsi di script
   fragili, gestione esplicita di stato (start/stop). Registrato in
   `ProtocolHandler.xcu` + `manifest.xml`.

2. **URL script macro** (`vnd.sun.star.script:...`) — più rapido da prototipare ma
   più fragile su path/location e meno adatto a uno stato persistente.

L'ID implementazione in `dettatura.py` (`IMPL_NAME`), il nodo in
`ProtocolHandler.xcu` e l'`identifier` in `description.xml` devono restare
**coerenti**: sono il collante tra i file.

---

## 6. Threading e API UNO

L'acquisizione audio gira in un `threading.Thread` daemon: la UI di LO non si
blocca mai. L'inserimento testo avviene via view-cursor:

```python
doc = frame.getController().getModel()
view_cursor = doc.getCurrentController().getViewCursor()
doc.getText().insertString(view_cursor, testo, False)
```

> ⚠️ **Nota di robustezza:** UNO non è formalmente thread-safe. Inserire dal thread
> worker funziona nella pratica per testo breve, ma l'approccio più sicuro è
> marshalare l'update sul thread principale (es. un `com.sun.star.awt.XCallback` /
> timer idle). Migliorìa pianificata — vedi [STATO_PROGETTO.md](STATO_PROGETTO.md).

---

## 7. Coesistenza multilingua (it, en, …)

Le estensioni di lingue diverse possono essere **installate insieme**. Perché
LibreOffice le tenga separate, ogni loro identificatore di registro dev'essere
**univoco**. I sorgenti usano prefissi coerenti; `scripts/_pack.py` inietta il
codice lingua a build-time:

```
org.libreitalia.dettaturavocale   ->  org.libreitalia.dettaturavocale.<lang>
vnd.libreitalia.dettatura:        ->  vnd.libreitalia.dettatura.<lang>:
```

Con due sole sostituzioni diventano distinti **tutti insieme**: `identifier`
(description.xml), `IMPL_NAME`/`PROTOCOL`/`EXTENSION_ID` (dettatura.py), il nodo
`HandlerSet` (ProtocolHandler.xcu) e i nodi menu/toolbar/image (Addons.xcu).
Restano coerenti tra loro (è il collante descritto in §5). Quindi
`getPackageLocation(EXTENSION_ID)` di §4 a runtime riceve l'id giusto `.<lang>`.

### Mutua esclusione a runtime (lockfile)
Coesistere installate **non** vuol dire poter ascoltare il microfono insieme: due
motori Vosk sullo stesso input si pestano. Visto che IT ed EN girano nello stesso
processo `soffice`, un **lockfile dal nome FISSO** (non per-lingua) li coordina:

```
<tmp>/voice-dictation.lock        # contiene: PID + identifier del titolare
```

`dettatura.py` allo START chiama `_acquisisci_lock()`: se un'istanza **viva**
detiene il lock (PID controllato in modo cross-platform, niente `os.kill` su
Windows), rifiuta e avvisa l'utente. Allo STOP / a fine motore chiama
`_rilascia_lock()` (rimuove solo se il lock è suo). I lock **stantii** (processo
morto dopo un crash) vengono riconosciuti e sovrascritti.
