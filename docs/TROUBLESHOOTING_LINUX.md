# Risoluzione problemi — Linux

Guida ai problemi più comuni della Dettatura Vocale su Linux.
Prima regola: **leggi il log**. Writer → menu **Dettatura → Apri cartella dei log** →
apri `dettatura_libreoffice.log` (di solito in `/tmp`).

---

## 0. Come leggere il log

A ogni avvio scrive una sezione `--- DIAGNOSTICA ---` e poi, mentre ascolti:

```
ascolto avviato
blocco=1  livello=1   parziale=''
blocco=26 livello=8200 parziale='ciao come'
```

- **`livello`** = volume audio in arrivo (scala 0–32767).
  - ~0–2 → **silenzio**: il microfono non manda segnale (vedi §1).
  - alto ma `parziale=''` → audio ok ma Vosk non capisce (vedi §4).
- **`parziale`** = riconoscimento in tempo reale.
- Se `blocco=...` **non compare** → l'audio non parte (vedi §2).

---

## 1. Vedo l'icona ma non scrive niente (log: `livello=1`)

Microfono muto o sorgente sbagliata.

1. **Volume/mute del microfono**
   ```bash
   pavucontrol         # scheda "Dispositivi di ingresso": alza il volume, togli il mute
   # oppure:
   alsamixer           # F4 per Capture, alza, M per togliere mute
   ```
   Parla e guarda se la barra di livello in `pavucontrol` si muove. Se non si muove,
   il problema è il microfono di sistema, non il programma.

2. **Sorgente di ingresso giusta**
   In `pavucontrol` → scheda **Configurazione**, scegli il profilo corretto della
   scheda audio; in **Ingresso**, seleziona il microfono giusto come predefinito.
   Mentre la dettatura è attiva, nella scheda **Registrazione** vedrai
   "ALSA plug-in [soffice.bin]": lì puoi reindirizzarlo sul mic giusto.

3. **PipeWire/PulseAudio attivo**
   ```bash
   pactl info | grep "Server Name"   # deve rispondere (PulseAudio o PipeWire)
   ```
   Se non c'è server audio, sounddevice non trova ingressi.

---

## 2. La dettatura non parte / errore nel log

Cerca `ERRORE` o `ECCEZIONE` nel log.

- `ERRORE import sounddevice (PortAudio?)` → manca **PortAudio** di sistema.
  Su Linux la wheel di sounddevice usa la libreria di sistema:
  ```bash
  # Debian/Ubuntu
  sudo apt install libportaudio2
  # Fedora
  sudo dnf install portaudio
  # Arch
  sudo pacman -S portaudio
  ```
- `ERRORE import vosk` → controlla nella DIAGNOSTICA che `native in vosk/` elenchi
  `libvosk.so`. Se manca, la oxt è incompleta: reinstalla quella della Release.
- `modello Vosk non trovato` → la cartella `model/` non è stata estratta. Reinstalla.

---

## 3. `_cffi_backend` per la mia versione di Python

La oxt include `_cffi_backend` per Python **3.9–3.14**. Controlla nella DIAGNOSTICA la
riga `python=...`: se la tua versione è ≤ 3.8 (LibreOffice molto vecchio), non è
supportata — aggiorna LibreOffice. Su Arch (Python 3.14) è già coperto.

Verifica quale Python usa il TUO LibreOffice:
```
Strumenti → Macro → Modifica macro → finestra Shell, oppure leggi 'python=' nel log
```

---

## 4. Scrive a caso / non capisce

- Modello della **lingua giusta**? `-it-` = italiano, `-en-` = inglese.
- Parla a ritmo normale, vicino al microfono, ambiente non rumoroso.
- Il modello "small" è veloce ma non perfetto: qualche errore è normale.

---

## 5. Il pulsante non compare

- Devi essere in **Writer** (non Calc/Impress).
- Riavvia LibreOffice dopo l'installazione.
- In alternativa al pulsante in toolbar, usa il menu **Dettatura**.
- Verifica in Strumenti → Gestione estensioni che risulti installata.

---

## 6. Italiano e inglese insieme

Convivono come estensioni separate (due pulsanti). **Non ascoltano insieme**: se ne
avvii una mentre l'altra è attiva, compare un avviso. Fermane una prima dell'altra.

---

## Ancora bloccato?

Apri una issue su GitHub allegando le righe del log da `ascolto avviato` a
`ascolto fermato` (inclusa la DIAGNOSTICA) e l'output di `pactl info` e
`pavucontrol`.
