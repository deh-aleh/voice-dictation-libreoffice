# Stato del progetto

Aggiornato: **2026-06-20** · Versione: **0.2.0**

---

## Sintesi

L'estensione è **funzionante su LibreOffice reale** (Linux x86_64, Python 3.14).
Il ciclo completo — click → ascolto → riconoscimento Vosk → punteggiatura/numeri/
comandi → inserimento al cursore — è stato verificato. Il sistema di build e deploy
multipiattaforma (3 OS × 2 lingue, CI GitHub Actions) è pronto.

Legenda: ✅ fatto e testato · 🟡 implementato, non testato su tutti gli OS · ⬜ da fare

---

## Stato per componente

| Area                                         | Stato | Note |
|----------------------------------------------|:----:|------|
| Struttura cartelle / layout `.oxt`           | ✅ | radice = `src/`, build via staging |
| `description.xml`                            | ✅ | id `.<lang>` iniettato; `<platform>` per-OS; versione da tag git |
| `META-INF/manifest.xml`                      | ✅ | registra componente + 2 `.xcu` |
| `Addons.xcu` (pulsante toolbar)              | ✅ | contesto limitato a Writer; icona verde/rossa |
| `ProtocolHandler.xcu`                        | ✅ | protocollo `vnd.libreitalia.dettatura.<lang>:*` |
| `dettatura.py` — handler UNO                 | ✅ | XDispatch + XServiceInfo + XInitialization |
| `dettatura.py` — thread audio                | ✅ | daemon thread, non blocca UI |
| `dettatura.py` — Vosk streaming              | ✅ | `KaldiRecognizer`, blocchi 16 kHz |
| `dettatura.py` — inserimento al cursore      | ✅ | view-cursor via UNO, testato su LO reale |
| `dettatura.py` — lockfile mutua escl.        | ✅ | `voice-dictation.lock`, cross-platform |
| `trasformazione.py` — punteggiatura a voce   | ✅ | `punteggiatura_map` editabile, 23 simboli |
| `trasformazione.py` — numeri in cifre        | ✅ | it/en, forme concatenate e separate |
| Comandi vocali formattazione                 | ✅ | grassetto/corsivo/sottolineato/maiuscole/liste/allineamento/font/stampa/undo/redo/data |
| Toggle numeri / punteggiatura / comandi      | ✅ | indipendenti, persistiti in config |
| Dizionari editabili (comandi + punteggiatura)| ✅ | `comandi_map` / `punteggiatura_map` in config JSON, riletti a ogni avvio |
| Flag `verbose` / `debug` / `verbose-logging` | ✅ | popup e log per diagnostica |
| Log rotation (~4 MB)                         | ✅ | file separato per lingua in cartella condivisa |
| Caricamento robusto `trasformazione.py`      | ✅ | `importlib` + nome univoco per lingua (no cache stantia, no collisioni it/en) |
| Script di build (`scripts/`, Makefile)       | ✅ | parametrici per lingua/piattaforma |
| Bundling dipendenze native                   | ✅ | `fetch_deps.sh`; Linux x86_64 verificato |
| `_cffi_backend` multi-versione 3.9–3.14      | ✅ | risolve mismatch CPython/LO; verificato su Python 3.14 |
| Bundling modello Vosk (it/en)                | ✅ | `fetch_model.sh <lang>` (~50 MB) |
| Coesistenza it + en installate               | ✅ | identifier/protocollo distinti per lingua |
| Icone pulsante (`mic_16/26.png`)             | ✅ | varianti per lingua in `src/icons/` |
| CI GitHub Actions (matrice 3 OS × 2 lingue)  | 🟡 | configurazione pronta; run reale su Windows/macOS non ancora eseguito |
| Test su LibreOffice reale — Linux            | ✅ | ciclo start/stop, inserimento testo, comandi, toggle verificati |
| Test su LibreOffice reale — Windows/macOS    | ⬜ | non ancora |

---

## Cosa funziona oggi

- **Dettatura su LibreOffice Writer** (Linux x86_64): avvio, riconoscimento Vosk in
  streaming, inserimento al cursore, stop — verificati su LibreOffice reale.
- **Punteggiatura, numeri e comandi** a voce funzionanti e testati.
- **Toggle** indipendenti con config JSON persistita e ricaricata senza riavvio.
- **Build parametrica**: `make all LANG=it|en PLATFORM=...` produce
  `dist/voice-dictation-<lang>-<platform>.oxt`. Verificata su Linux x86_64.
- **`_cffi_backend` multi-versione**: funzionante su Python 3.14 (Arch Linux).
- **CI** `release.yml`: configurazione pronta (3 OS × 2 lingue = 6 oxt su tag).

---

## Roadmap

### v0.2 — "funziona su LibreOffice reale"  ✅ completata
- [x] Build parametrica lingua × piattaforma.
- [x] Deploy multipiattaforma via CI + coesistenza it/en + lockfile.
- [x] Punteggiatura, numeri e comandi vocali.
- [x] Toggle indipendenti + config editabile.
- [x] Testato su LibreOffice reale (Linux).

### v0.3 — robustezza e portabilità
- [ ] Marshalare l'inserimento testo sul thread principale (timer/idle UNO)
      per maggiore robustezza thread-safety (vedi ARCHITETTURA.md §6).
- [ ] Gestione errori microfono / device assente con messaggio chiaro all'utente.
- [ ] Validare la CI su Windows e macOS (primo run reale su tag).
- [ ] Selezione device audio da una finestra opzioni.
- [ ] Testare coesistenza it+en su LibreOffice reale.

### v1.0
- [ ] Pubblicazione su LibreOffice Extensions.
- [ ] Supporto altre lingue (riuso del meccanismo it/en).
- [ ] UI opzioni (selezione modello, device audio, step font).

---

## Rischi noti

1. **Thread-safety UNO** — inserimento dal worker funziona nella pratica ma non è
   formalmente garantito; da risolvere in v0.3 con marshal sul thread principale.
2. **Build Windows/macOS** — la matrice CI non è stata eseguita su runner reali;
   potrebbe emergere qualche incompatibilità di path o wheel.
3. **Python ≤ 3.8** — fuori dal supporto (`cffi 2.0.0` parte da cp39).
