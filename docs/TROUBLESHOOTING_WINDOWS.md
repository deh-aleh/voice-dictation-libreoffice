# Risoluzione problemi — Windows

Guida ai problemi più comuni della Dettatura Vocale su Windows.
Prima regola: **leggi il log**. Writer → menu **Dettatura → Apri cartella dei log** →
apri `dettatura_libreoffice.log` (in `C:\Users\<tu>\AppData\Local\Temp`).

---

## 0. Come leggere il log

A ogni avvio della dettatura il log scrive una sezione `--- DIAGNOSTICA ---` e poi,
mentre ascolti, righe tipo:

```
ascolto avviato
blocco=1  livello=1   parziale=''
blocco=26 livello=8200 parziale='ciao come'
```

- **`livello`** = volume dell'audio in arrivo (scala 0–32767).
  - `livello` ~0–2 → **silenzio**: il microfono non manda segnale (vedi §1).
  - `livello` alto ma `parziale=''` → audio ok ma Vosk non capisce (vedi §4).
- **`parziale`** = cosa Vosk sta riconoscendo in tempo reale.
- Se `blocco=...` **non compare affatto** → l'audio non parte (vedi §2).

---

## 1. Vedo l'icona del microfono ma non scrive niente

Quasi sempre è **audio muto**. Nel log vedrai `livello=1` (o ~0). Controlla in ordine:

1. **Microfono mutato o a volume 0**
   Impostazioni → Sistema → Audio → Input → seleziona il tuo microfono →
   controlla che **non sia mutato** e che il **volume non sia a 0**. Parla e guarda
   la barra **"Prova il microfono"**: se non si muove, il problema è qui (non nel
   programma).

2. **Privacy del microfono**
   Impostazioni → Privacy e sicurezza → Microfono:
   - "Accesso al microfono" = **Attivato**
   - "Consenti alle app di accedere al microfono" = **Attivato**
   - in fondo: **"Consenti alle app desktop di accedere al microfono" = Attivato**
     (LibreOffice è un'app desktop: questa voce è quella che lo blocca).
   Dopo aver cambiato, **chiudi del tutto LibreOffice** (anche l'avvio rapido nella
   tray) e riapri.

3. **Microfono predefinito sbagliato**
   Se hai più ingressi (webcam, cuffie, array integrato), Windows potrebbe usarne
   uno spento. Imposta come **predefinito** quello giusto in Impostazioni → Audio →
   Input, poi riavvia LibreOffice.

> Verifica veloce: se la barra "Prova il microfono" di Windows si muove ma il log
> mostra `livello=1`, allora il mic è ok ma LibreOffice non lo riceve → ricontrolla
> il punto 2 (privacy app desktop).

---

## 2. La dettatura non parte / nel log compare un errore

Apri il log e cerca `ERRORE` o `ECCEZIONE`.

- `ERRORE import vosk` → DLL native non caricate. Verifica nella DIAGNOSTICA che
  `native in vosk/` elenchi `libvosk.dll`, `libstdc++-6.dll`, `libgcc_s_seh-1.dll`,
  `libwinpthread-1.dll`. Se mancano, la oxt è incompleta: reinstalla quella della
  Release ufficiale.
- `ERRORE import sounddevice (PortAudio?)` → verifica `_sounddevice_data presente: True`
  nella DIAGNOSTICA. Se è `False`, la oxt è incompleta: reinstalla.
- `modello Vosk non trovato` → la cartella `model/` non è stata estratta. Reinstalla.

---

## 3. Ho installato la oxt ma non vedo il pulsante

- Devi essere in **Writer** (il pulsante è solo lì, non in Calc/Impress).
- Riavvia LibreOffice dopo l'installazione.
- Se non lo trovi in toolbar, usa il menu **Dettatura** nella barra dei menu.
- Estensione installata? Strumenti → Gestione estensioni: deve comparire
  "Voice Dictation (Vosk - …)".

---

## 4. Scrive a caso / non capisce le parole

- `livello` alto ma testo sbagliato: stai usando il modello della **lingua giusta**?
  L'estensione `-it-` capisce italiano, `-en-` inglese. Installa quella corretta.
- Parla a ritmo normale, vicino al microfono, in ambiente non troppo rumoroso.
- Il modello "small" è veloce ma non perfetto: errori occasionali sono normali.

---

## 5. Posso installare italiano e inglese insieme?

Sì. Sono estensioni separate (`voice-dictation-it-…` e `-en-…`) e convivono. Avrai
due pulsanti. **Non possono ascoltare insieme**: se ne avvii una mentre l'altra è in
ascolto, compare un avviso. Fermane una prima di usare l'altra.

---

## Ancora bloccato?

Apri una issue su GitHub allegando le righe del log da `ascolto avviato` fino a
`ascolto fermato` (inclusa la sezione DIAGNOSTICA). Quei dati bastano per capire il
problema.
