# Stato del progetto

Aggiornato: **2026-06-11** · Versione: **0.2.0-dev**

---

## Sintesi

Lo **scheletro completo** dell'estensione è pronto, e ora è pronto anche il
**sistema di deploy multipiattaforma e multilingua**: build parametrica
(lingua × OS), `_cffi_backend` multi-versione per la compatibilità col Python di
LibreOffice, coesistenza it/en con lockfile, e CI GitHub Actions che produce 6
oxt su tag. Manca il **test su LibreOffice reale** (mai installato/eseguito).

Legenda: ✅ fatto · 🟡 parziale · ⬜ da fare

---

## Stato per componente

| Area                                   | Stato | Note |
|----------------------------------------|:----:|------|
| Struttura cartelle / layout `.oxt`     | ✅ | radice = `src/`, build via staging |
| `description.xml`                       | ✅ | id `.<lang>` iniettato; `<platform>` per-OS |
| `META-INF/manifest.xml`                 | ✅ | registra componente + 2 `.xcu` |
| `Addons.xcu` (pulsante toolbar)         | ✅ | contesto limitato a Writer |
| `ProtocolHandler.xcu`                   | ✅ | protocollo `vnd.libreitalia.dettatura.<lang>:*` |
| `dettatura.py` — handler UNO            | ✅ | XDispatch + XServiceInfo + XInitialization |
| `dettatura.py` — thread audio           | ✅ | daemon thread, non blocca UI |
| `dettatura.py` — Vosk streaming         | ✅ | `KaldiRecognizer`, blocchi 16kHz |
| `dettatura.py` — inserimento al cursore | ✅ | view-cursor via UNO |
| `dettatura.py` — lockfile mutua escl.   | ✅ | `voice-dictation.lock`, cross-platform |
| Script di build (`scripts/`, Makefile)  | ✅ | parametrici per lingua/piattaforma |
| Bundling dipendenze native              | ✅ | `fetch_deps.sh`; Linux x86_64 verificato |
| `_cffi_backend` multi-versione 3.9-3.14 | ✅ | risolve il mismatch CPython/LO |
| Bundling modello Vosk (it/en)           | ✅ | `fetch_model.sh <lang>` (~50 MB) |
| Multipiattaforma (per-OS via CI)        | ✅ | matrice ubuntu/windows/macos su tag `v*` |
| Coesistenza it + en installate          | ✅ | identifier/protocollo distinti per lingua |
| Icone pulsante (`mic_16/26.png`)        | ✅ | presenti in `src/icons/` |
| Test su LibreOffice reale               | ⬜ | mai installato/eseguito ancora |

---

## Cosa funziona oggi

- Build parametrica: `make all LANG=it|en PLATFORM=...` produce
  `dist/voice-dictation-<lang>-<platform>.oxt`. **Verificato su Linux x86_64**
  (it ed en, struttura ZIP e sostituzioni controllate).
- CI `release.yml`: 3 OS × 2 lingue = 6 oxt → GitHub Release su tag.
- Architettura click → dispatch → lock → thread → inserimento completa nel codice.

## Cosa NON è ancora verificato

- Caricamento effettivo del componente Python da parte di pyuno su LO reale.
- Import di `vosk`/`sounddevice` dal `pythonpath/` dentro il Python di LibreOffice.
- Selezione automatica del `_cffi_backend` giusto sul Python reale di LO.
- Latenza/accuratezza del riconoscimento in tempo reale.
- Build effettiva sui runner Windows/macOS (finora solo Linux locale).

---

## Roadmap

### v0.2 — "gira sulla mia macchina"  (deploy: ✅)
- [x] Build parametrica lingua × piattaforma.
- [x] Deploy multipiattaforma via CI + coesistenza it/en + lockfile.
- [ ] Installare su LibreOffice reale e testare il ciclo start/stop.
- [ ] Verificare l'inserimento al cursore con testo lungo.

### v0.3 — robustezza
- [ ] Marshalare l'inserimento testo sul thread principale (timer/idle UNO)
      invece che dal worker (vedi ARCHITETTURA.md §6).
- [ ] Gestione errori microfono / device assente.
- [ ] Selezione device audio e modello da una finestra opzioni.
- [ ] Primo run CI reale su tag e verifica delle 6 oxt.

### v1.0
- [ ] Punteggiatura vocale ("virgola", "punto", "a capo").
- [ ] Comandi vocali ("cancella", "nuovo paragrafo").
- [ ] Altre lingue (riuso del meccanismo it/en).
- [ ] Pubblicazione su LibreOffice Extensions.

---

## Rischi noti

1. **Thread-safety UNO** — inserimento dal worker da rendere più robusto (§6).
2. **Versione CPython** — mitigato col bundle `_cffi_backend` 3.9–3.14; Python ≤3.8
   (LibreOffice molto vecchi) resta fuori.
3. **Build Windows/macOS non ancora eseguita** — la matrice CI va validata con un
   primo run reale.
