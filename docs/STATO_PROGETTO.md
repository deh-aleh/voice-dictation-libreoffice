# Stato del progetto

Aggiornato: **2026-06-10** · Versione: **0.1.0 (scaffold)**

---

## Sintesi

Lo **scheletro completo** dell'estensione è pronto e coerente: configurazione UNO
(toolbar + routing) e componente Python (handler + motore Vosk + inserimento al
cursore). Mancano: i **binari/modello** da bundlare, le **icone**, e i **test su
LibreOffice reale**.

Legenda: ✅ fatto · 🟡 parziale · ⬜ da fare

---

## Stato per componente

| Area                                   | Stato | Note |
|----------------------------------------|:----:|------|
| Struttura cartelle / layout `.oxt`     | ✅ | radice = `src/` |
| `description.xml`                       | ✅ | id `org.libreitalia.dettaturavocale` |
| `META-INF/manifest.xml`                 | ✅ | registra componente + 2 `.xcu` |
| `Addons.xcu` (pulsante toolbar)         | ✅ | contesto limitato a Writer |
| `ProtocolHandler.xcu`                   | ✅ | protocollo `vnd.libreitalia.dettatura:*` |
| `dettatura.py` — handler UNO            | ✅ | XDispatch + XServiceInfo + XInitialization |
| `dettatura.py` — thread audio           | ✅ | daemon thread, non blocca UI |
| `dettatura.py` — Vosk streaming         | ✅ | `KaldiRecognizer`, blocchi 16kHz |
| `dettatura.py` — inserimento al cursore | ✅ | view-cursor via UNO |
| Script di build (`scripts/`, Makefile)  | ✅ | deps / model / oxt |
| Bundling dipendenze native              | ⬜ | richiede esecuzione `make deps` per OS |
| Bundling modello Vosk IT                | ⬜ | `make model` (~50 MB) |
| Icone pulsante (`mic_16/26.png`)        | ⬜ | placeholder testuale intanto |
| Test su LibreOffice reale               | ⬜ | mai installato/eseguito ancora |
| Multipiattaforma (fat oxt o per-OS)     | ⬜ | strategia scelta in ARCHITETTURA.md §3 |

---

## Cosa funziona oggi

- Build dell'`.oxt` produce un pacchetto installabile (senza deps/modello → la
  dettatura segnala errore gestito all'avvio, l'estensione si installa lo stesso).
- L'architettura del click → dispatch → thread → inserimento è completa nel codice.

## Cosa NON è ancora verificato

- Caricamento effettivo del componente Python da parte di pyuno su LO reale.
- Import di `vosk`/`sounddevice` dal `pythonpath/` dentro il Python di LibreOffice.
- Latenza/accuratezza del riconoscimento in tempo reale.
- Compatibilità versione CPython tra wheel e LO.

---

## Roadmap

### v0.2 — "gira sulla mia macchina"
- [ ] `make deps && make model && make oxt` su Linux x86_64.
- [ ] Installare su LibreOffice reale e testare il ciclo start/stop.
- [ ] Verificare l'inserimento al cursore con testo lungo.
- [ ] Aggiungere le 3 icone PNG.

### v0.3 — robustezza
- [ ] Marshalare l'inserimento testo sul thread principale (timer/idle UNO)
      invece che dal worker (vedi ARCHITETTURA.md §6).
- [ ] Feedback visivo stato "in ascolto" (toggle state sul pulsante).
- [ ] Gestione errori microfono / device assente.
- [ ] Selezione device audio e modello da una finestra opzioni.

### v0.4 — multipiattaforma
- [ ] CI con matrice OS (Linux/Windows/macOS) per generare `pythonpath/` per-OS.
- [ ] Scegliere strategia A (per-OS) o B (fat oxt) — ARCHITETTURA.md §3.
- [ ] Release automatica degli `.oxt` su GitHub Releases.

### v1.0
- [ ] Punteggiatura vocale ("virgola", "punto", "a capo").
- [ ] Comandi vocali ("cancella", "nuovo paragrafo").
- [ ] Pubblicazione su LibreOffice Extensions.

---

## Rischi noti

1. **Binari nativi per piattaforma** — il vincolo "all-in-one" è realizzabile ma
   impone build per-OS. È il principale lavoro aperto.
2. **Thread-safety UNO** — inserimento dal worker da rendere più robusto.
3. **Versione CPython** — mismatch wheel/LO può rompere l'import dei binari.
