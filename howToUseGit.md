# Come usare Git — comandi principali

Guida rapida ai comandi che servono di più, più i "particolari" (tag, release).
Esempi calibrati su questo progetto (`voice-dictation-libreoffice`).

---

## 1. Il ciclo base (ogni giorno)

```bash
git status                 # cosa è cambiato (rosso = non in staging, verde = in staging)
git add <file>             # mette un file in staging (pronto al commit)
git add -A                 # mette TUTTO (nuovi, modificati, cancellati)
git commit -m "messaggio"  # salva uno snapshot in locale
git push                   # invia i commit a GitHub (origin)
```

Flusso tipico: `git add -A` → `git commit -m "..."` → `git push`.

> `commit` salva **in locale**. Finché non fai `push`, su GitHub non si vede nulla.

---

## 2. Guardare cosa è successo

```bash
git log --oneline -10      # ultimi 10 commit, una riga ciascuno
git log --oneline --graph  # con il grafo dei rami
git diff                   # differenze NON ancora in staging
git diff --staged          # differenze già in staging (cosa committeresti)
git show <hash>            # dettaglio di un commit specifico
```

---

## 3. Annullare / correggere

```bash
git restore <file>             # scarta le modifiche locali a un file (ATTENZIONE: si perdono)
git restore --staged <file>    # toglie un file dallo staging (ma tiene le modifiche)
git commit --amend -m "nuovo"  # corregge l'ULTIMO commit (messaggio o contenuto)
git revert <hash>              # crea un nuovo commit che annulla un commit passato
```

> Usa `--amend` solo se NON hai ancora pushato quel commit.

---

## 4. Branch (rami)

```bash
git branch                 # elenca i rami (l'asterisco = quello attuale)
git switch -c nuova-feature  # crea e passa a un nuovo ramo
git switch master          # torna al ramo principale
git merge nuova-feature    # unisce 'nuova-feature' nel ramo attuale
git push -u origin nuova-feature  # pubblica il ramo la prima volta
```

Perché: lavori su una feature senza toccare `master`, poi la unisci.

---

## 5. Sincronizzare con GitHub

```bash
git pull                   # scarica e integra le modifiche dal remoto
git fetch                  # scarica SENZA integrare (solo aggiorna i riferimenti)
git remote -v              # mostra l'URL del remoto (origin)
```

---

## 6. I TAG (i "particolari") — e la release

Un **tag** è un'etichetta fissa su un commit: marca una versione (es. `v0.2.0`).
In questo progetto **la GitHub Release parte SOLO quando pushi un tag `v*`**
(lo dice `.github/workflows/release.yml`).

```bash
git tag                        # elenca i tag esistenti
git tag v0.2.0                 # crea un tag "leggero" sul commit attuale
git tag -a v0.2.0 -m "Release 0.2.0"   # tag "annotato" (con messaggio, consigliato)
git push origin v0.2.0         # PUSHA il tag -> fa partire la CI e crea la Release
git push --tags                # pusha TUTTI i tag in una volta
```

> ⚠️ `git push` normale **non** invia i tag: vanno pushati a parte.

### Far partire una release (questo progetto)
```bash
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0
```
→ GitHub Actions builda le 6 `.oxt` (it/en × Linux/Windows/macOS) e le allega a
una Release. Conviene allineare il numero a `version` in `src/description.xml`.

### Cancellare un tag (se hai sbagliato)
```bash
git tag -d v0.2.0              # cancella il tag in locale
git push origin :refs/tags/v0.2.0   # cancella il tag anche su GitHub
```

---

## 7. Comandi utili sparsi

```bash
git stash                  # mette da parte le modifiche in corso (le "nasconde")
git stash pop              # le rimette
git clean -nd              # mostra i file non tracciati che verrebbero rimossi (-n = prova)
git clean -fd              # li rimuove davvero (ATTENZIONE)
git blame <file>           # chi/quale commit ha scritto ogni riga
```

---

## Schema mentale

```
modifiche  --git add-->  staging  --git commit-->  storia locale  --git push-->  GitHub
                                                         |
                                                    git tag + push origin <tag>  -->  Release (CI)
```
