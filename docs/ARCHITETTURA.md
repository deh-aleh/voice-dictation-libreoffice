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

Punto chiave: la radice dell'archivio coincide con `src/`. Lo zip **non** deve
contenere una cartella `src/` di livello superiore. Vedi `scripts/build_oxt.sh`
(`cd src && zip -r out.oxt .`).

---

## 2. Caricare librerie Python dall'`.oxt`: la cartella `pythonpath/`

**Meccanismo nativo di LibreOffice** (questa è la "best practice" richiesta):

> Quando LibreOffice carica un **componente Python da un'estensione**, aggiunge
> automaticamente la sottocartella `pythonpath/` di quell'estensione a
> `sys.path`.

Conseguenza pratica: qualsiasi pacchetto messo in `src/pythonpath/` diventa
importabile dal componente **senza** che l'utente installi nulla con `pip`.

```
src/pythonpath/
├── vosk/
├── sounddevice.py
├── _sounddevice.py
├── cffi/
├── _cffi_backend.*.so
└── vosk/libvosk.so          # binario nativo del motore
```

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
Quindi un singolo `.oxt` "all-in-one" è davvero universale **solo se** include i
binari di **tutte** le piattaforme target.

### Strategia A — un `.oxt` per piattaforma (consigliata)
Pubblicare release separate:
`dettatura-vocale-linux-x86_64.oxt`, `-windows-x86_64.oxt`, `-macos-arm64.oxt`.
Ogni build esegue `make deps` sulla piattaforma corrispondente (o usa CI con
matrice di OS). `description.xml` può dichiarare la `<platform>` specifica.

### Strategia B — un `.oxt` universale "fat"
Mantenere binari per più piattaforme in sottocartelle e selezionarli a runtime
aggiungendo la cartella giusta a `sys.path` in cima a `dettatura.py`:

```python
import os, sys, platform
_here = os.path.dirname(__file__)
_plat = "%s-%s" % (platform.system().lower(), platform.machine().lower())
_libs = os.path.join(_here, "pythonpath", _plat)
if os.path.isdir(_libs):
    sys.path.insert(0, _libs)
```

Con layout:
```
pythonpath/
├── linux-x86_64/
├── windows-amd64/
└── darwin-arm64/
```
Costo: `.oxt` molto più pesante. Vantaggio: installazione unica.

### Compatibilità versione Python
Le wheel native sono legate alla minor di CPython (es. cp310). Il Python interno
di LibreOffice ha una sua versione. **Best practice:** generare le wheel con una
versione di Python ≈ quella di LO (verificabile con `Strumenti > Macro >
Modifica > Shell`, oppure dal log). Wheel `abi3` (stable ABI), quando
disponibili, riducono il problema.

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
