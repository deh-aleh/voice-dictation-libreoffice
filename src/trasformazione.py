# -*- coding: utf-8 -*-
"""
trasformazione.py - Post-elaborazione del testo riconosciuto da Vosk.

Vosk restituisce testo "grezzo": tutto minuscolo, parole separate da spazi,
senza punteggiatura ne' cifre (i numeri sono dettati a voce). Qui:

  1. PUNTEGGIATURA: le parole-comando ("punto", "virgola", "punto e virgola",
     "apri parentesi", "nuovo paragrafo", ...) diventano il carattere giusto,
     con la spaziatura corretta (niente spazio prima di "." o ")", niente
     spazio dopo "(" , niente spazi attorno a "-" o "/", ecc.).

  2. NUMERI: le sequenze di numeri dettati ("venti tre", "duecentotrenta",
     "tremila cinquecento") diventano cifre ("23", "230", "3500").

Punto d'ingresso unico: trasforma(testo) -> str.
Nessuna dipendenza esterna: gira anche sotto il loader UNO di LibreOffice.
"""

# ---------------------------------------------------------------------------
# Punteggiatura.
# Ogni voce: frase_dettata -> (carattere, spazio_prima, spazio_dopo)
# I flag dicono se e' AMMESSO uno spazio su quel lato del carattere.
#   "."  -> spazio_prima=False, spazio_dopo=True   => "ciao. parola"
#   "("  -> spazio_prima=True,  spazio_dopo=False  => "ciao (parola"
#   "-"  -> entrambi False                         => "bianco-nero"
#   "\n" -> entrambi False                         => nessuno spazio attorno
# Le frasi multi-parola vanno messe qui: il match e' greedy (3 -> 2 -> 1 parole).
# ---------------------------------------------------------------------------
PUNTEGGIATURA = {
    "punto e virgola":     (";",    False, True),
    "punto interrogativo": ("?",    False, True),
    "punto esclamativo":   ("!",    False, True),
    "due punti":           (":",    False, True),
    "nuova linea":         ("\n",   False, False),
    "nuovo paragrafo":     ("\n\n", False, False),
    "apri parentesi":      ("(",    True,  False),
    "chiudi parentesi":    (")",    False, True),
    "apri virgolette":     ("\"",   True,  False),
    "chiudi virgolette":   ("\"",   False, True),
    "punto":               (".",    False, True),
    "virgola":             (",",    False, True),
    "trattino":            ("-",    False, False),
    "lineetta":            ("—", True, True),   # — (em dash)
    "asterisco":           ("*",    True,  True),
    "barra":               ("/",    False, False),
}

# Numero massimo di parole in una frase di punteggiatura (per il match greedy).
_MAX_FRASE = max(len(f.split()) for f in PUNTEGGIATURA)


# ---------------------------------------------------------------------------
# Numeri (italiano).
# ---------------------------------------------------------------------------
_UNITA = {
    "zero": 0, "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11,
    "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
    "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19,
}
_DECINE = {
    "venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50,
    "sessanta": 60, "settanta": 70, "ottanta": 80, "novanta": 90,
}


def _costruisci_atomi():
    """Tabella parola->valore per 0..99 (incluse le forme concatenate
    tipo 'ventuno', 'ventitre', 'trentotto')."""
    atomi = dict(_UNITA)
    atomi.update(_DECINE)
    for nome_d, val_d in _DECINE.items():
        for nome_u, val_u in _UNITA.items():
            if val_u == 0:
                continue
            # 'venti'+'uno' -> 'ventuno', 'trenta'+'otto' -> 'trentotto':
            # davanti a uno(1)/otto(8) la decina perde la vocale finale.
            prefisso = nome_d[:-1] if val_u in (1, 8) else nome_d
            atomi[prefisso + nome_u] = val_d + val_u
            if val_u == 3:  # 'ventitre' e anche 'ventitré'
                atomi[prefisso + "tré"] = val_d + val_u
    return atomi


_ATOMI = _costruisci_atomi()
_ATOMI["un"] = 1  # solo come prefisso interno (es. 'unmilione')


def _parola_numero(w):
    """Valore intero di UNA parola-numero italiana, o None se non lo e'.

    Decompone ricorsivamente sui moltiplicatori (milioni/mila/mille/cento),
    cosi' gestisce sia i token separati ('due', 'cento') sia quelli
    concatenati ('duecentotrentaquattro')."""
    if not w:
        return None
    if w in _ATOMI:
        return _ATOMI[w]

    # milioni / milione
    for sep in ("milioni", "milione"):
        if sep in w:
            sinistra, destra = w.split(sep, 1)
            ls = _parola_numero(sinistra) if sinistra else 1
            ds = _parola_numero(destra) if destra else 0
            if ls is not None and ds is not None:
                return ls * 1000000 + ds

    # mila / mille
    for sep in ("mila", "mille"):
        if sep in w:
            sinistra, destra = w.split(sep, 1)
            ls = _parola_numero(sinistra) if sinistra else 1
            ds = _parola_numero(destra) if destra else 0
            if ls is not None and ds is not None:
                return ls * 1000 + ds

    # cento
    if "cento" in w:
        sinistra, destra = w.split("cento", 1)
        ls = _parola_numero(sinistra) if sinistra else 1
        ds = _parola_numero(destra) if destra else 0
        if ls is not None and ds is not None:
            return ls * 100 + ds

    return None


def _combina_run(valori):
    """Combina i valori di token-numero consecutivi in un solo intero.
    Es. [2, 1000000] -> 2_000_000 ; [1000, 200] -> 1200 ; [200, 34] -> 234."""
    totale = 0
    corrente = 0
    for v in valori:
        if v == 100:
            corrente = (corrente or 1) * 100
        elif v == 1000:
            totale += (corrente or 1) * 1000
            corrente = 0
        elif v == 1000000:
            totale += (corrente or 1) * 1000000
            corrente = 0
        else:
            corrente += v
    return totale + corrente


def _leggi_numero(tokens, i):
    """Dalla posizione i, consuma i token-numero consecutivi.
    Ritorna (valore, quanti_token). (None, 0) se tokens[i] non e' un numero."""
    valori = []
    j = i
    while j < len(tokens):
        v = _parola_numero(tokens[j])
        if v is None:
            break
        valori.append(v)
        j += 1
    if not valori:
        return None, 0
    return _combina_run(valori), j - i


# ---------------------------------------------------------------------------
# Composizione finale.
# ---------------------------------------------------------------------------
def _unisci(items):
    """Concatena gli item (testo, spazio_prima, spazio_dopo) inserendo uno
    spazio fra due item solo se ENTRAMBI i lati adiacenti lo ammettono."""
    parti = []
    prec_dopo = False  # niente spazio in testa
    for testo, sp_prima, sp_dopo in items:
        if parti and prec_dopo and sp_prima:
            parti.append(" ")
        parti.append(testo)
        prec_dopo = sp_dopo
    return "".join(parti)


def trasforma(testo):
    """Converte una frase riconosciuta da Vosk applicando punteggiatura e
    numeri. Le parole normali restano invariate, con spaziatura standard."""
    if not testo:
        return testo
    tokens = testo.split()
    items = []
    i = 0
    n_tok = len(tokens)
    while i < n_tok:
        # 1) punteggiatura, match greedy dalla frase piu' lunga.
        trovato = False
        for n in range(min(_MAX_FRASE, n_tok - i), 0, -1):
            frase = " ".join(tokens[i:i + n])
            regola = PUNTEGGIATURA.get(frase)
            if regola is not None:
                car, sp_prima, sp_dopo = regola
                items.append((car, sp_prima, sp_dopo))
                i += n
                trovato = True
                break
        if trovato:
            continue

        # 2) numero (run di token-numero consecutivi).
        valore, consumati = _leggi_numero(tokens, i)
        if consumati > 0:
            items.append((str(valore), True, True))
            i += consumati
            continue

        # 3) parola normale.
        items.append((tokens[i], True, True))
        i += 1

    return _unisci(items)
