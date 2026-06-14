# -*- coding: utf-8 -*-
"""
trasformazione.py - Post-processing of the text recognized by Vosk.

Vosk returns "raw" text: all lowercase, words separated by spaces, no
punctuation and no digits (numbers are spoken aloud). Here we:

  1. PUNCTUATION: spoken command words ("punto"/"period", "virgola"/"comma",
     "nuovo paragrafo"/"new paragraph", ...) become the matching character,
     with correct spacing (no space before "." or ")", no space after "(",
     no spaces around "-" or "/", etc.).

  2. NUMBERS: spoken number sequences ("venti tre"/"twenty three",
     "duecentotrenta"/"two hundred thirty") become digits ("23", "230").
     Two adjacent independent numbers stay separate: "23 54" is NOT summed
     into "77" - each number is consumed on its own.

Single entry point: trasforma(testo) -> str.
No external dependencies: runs under the LibreOffice UNO loader as well.

Language is chosen by the build: scripts/_pack.py substitutes the @LANG@ token
below with "it" or "en". When running straight from src/ (dev/tests) the token
is left untouched, so we fall back to Italian.
"""

_LANG = "@LANG@"
if _LANG not in ("it", "en"):
    _LANG = "it"


# ---------------------------------------------------------------------------
# Punctuation tables.
# Each entry: spoken_phrase -> (char, space_before, space_after)
# The flags say whether a space is ALLOWED on that side of the character:
#   "."  -> space_before=False, space_after=True   => "ciao. parola"
#   "("  -> space_before=True,  space_after=False  => "ciao (parola"
#   "-"  -> both False                             => "bianco-nero"
#   "\n" -> both False                             => no space around it
# Multi-word phrases go here too: matching is greedy (longest phrase first).
# ---------------------------------------------------------------------------
_PUNCT_IT = {
    "punto e virgola":      (";",    False, True),
    "punto interrogativo":  ("?",    False, True),
    "punto esclamativo":    ("!",    False, True),
    "due punti":            (":",    False, True),
    "a capo":               ("\n",   False, False),
    "nuovo paragrafo":      ("\n\n", False, False),
    "apri parentesi":       ("(",    True,  False),
    "chiudi parentesi":     (")",    False, True),
    "apri virgolette":      ("\"",   True,  False),
    "chiudi virgolette":    ("\"",   False, True),
    "punto":                (". ",    False, False),
    "virgola":              (",",    False, True),
    "trattino":             ("-",    False, False),
    "lineetta":             ("—", True, True),   # — (em dash)
    "asterisco":            ("*",    True,  True),
    "barra":                ("/",    False, False),
    "chiocciola":           ("@",    False, False),
    "dollari":              ("$",    False, False),
    "euro":                 ("€",    False, False),
    "sterline":             ("£",    False, False),
    "percentuale":          ("%",    False, False),
    "hashtag":              ("#",    False, False),
    "puntini di sospensione":            ("...",    False, True),
    "eccetera":             ("etc. etc. ",    False, True),
}

_PUNCT_EN = {
    "full stop":            (".",    False, True),
    "period":               (".",    False, True),
    "comma":                (",",    False, True),
    "semicolon":            (";",    False, True),
    "colon":                (":",    False, True),
    "question mark":        ("?",    False, True),
    "exclamation mark":     ("!",    False, True),
    "exclamation point":    ("!",    False, True),
    "new line":             ("\n",   False, False),
    "new paragraph":        ("\n\n", False, False),
    "open parenthesis":     ("(",    True,  False),
    "open paren":           ("(",    True,  False),
    "close parenthesis":    (")",    False, True),
    "close paren":          (")",    False, True),
    "open quote":           ("\"",   True,  False),
    "open quotes":          ("\"",   True,  False),
    "close quote":          ("\"",   False, True),
    "close quotes":         ("\"",   False, True),
    "hyphen":               ("-",    False, False),
    "dash":                 ("—",    True,  True),
    "em dash":              ("—",    True,  True),
    "asterisk":             ("*",    True,  True),
    "slash":                ("/",    False, False),
    "at sign":              ("@",    False, False),
    "dollar sign":          ("$",    False, False),
    "dollars":              ("$",    False, False),
    "euro":                 ("€",    False, False),
    "pound sign":           ("£",    False, False),
    "pounds":               ("£",    False, False),
    "percent":              ("%",    False, False),
    "percentage sign":      ("%",    False, False),
    "hashtag":              ("#",    False, False),
    "number sign":          ("#",    False, False),
    "ellipsis":             ("...",  False, True),
    "etcetera":             ("etc. etc. ", False, True),
}

# ---------------------------------------------------------------------------
# Number atoms (word -> value).
# ---------------------------------------------------------------------------
_UNITA_IT = {
    "zero": 0, "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11,
    "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
    "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19,
}
_DECINE_IT = {
    "venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50,
    "sessanta": 60, "settanta": 70, "ottanta": 80, "novanta": 90,
}

_UNITS_EN = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS_EN = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def _costruisci_atomi_it():
    """word->value table for 0..99, including the Italian concatenated forms
    ('ventuno', 'ventitre', 'trentotto')."""
    atomi = dict(_UNITA_IT)
    atomi.update(_DECINE_IT)
    for nome_d, val_d in _DECINE_IT.items():
        for nome_u, val_u in _UNITA_IT.items():
            if val_u == 0:
                continue
            # before uno(1)/otto(8) the tens word drops its final vowel:
            # 'venti'+'uno' -> 'ventuno', 'trenta'+'otto' -> 'trentotto'.
            prefisso = nome_d[:-1] if val_u in (1, 8) else nome_d
            atomi[prefisso + nome_u] = val_d + val_u
            if val_u == 3:  # 'ventitre' and also 'ventitré'
                atomi[prefisso + "tré"] = val_d + val_u
    return atomi


_ATOMI_IT = _costruisci_atomi_it()
_ATOMI_IT["un"] = 1  # only as an internal prefix (e.g. 'unmilione')

_ATOMI_EN = dict(_UNITS_EN)
_ATOMI_EN.update(_TENS_EN)
_ATOMI_EN.update({"hundred": 100, "thousand": 1000, "million": 1000000})

# Bare multipliers: when one of these is a standalone token it SCALES the
# number being built instead of being added to it.
_MOLTIPLICATORI = (100, 1000, 1000000)


def _parola_numero_it(w):
    """Integer value of ONE Italian number-word, or None if not one.
    Recurses over the multipliers (milioni/mila/mille/cento) so it handles
    both separate tokens ('due', 'cento') and concatenated ones
    ('duecentotrentaquattro')."""
    if not w:
        return None
    if w in _ATOMI_IT:
        return _ATOMI_IT[w]

    for sep in ("milioni", "milione"):
        if sep in w:
            sinistra, destra = w.split(sep, 1)
            ls = _parola_numero_it(sinistra) if sinistra else 1
            ds = _parola_numero_it(destra) if destra else 0
            if ls is not None and ds is not None:
                return ls * 1000000 + ds

    for sep in ("mila", "mille"):
        if sep in w:
            sinistra, destra = w.split(sep, 1)
            ls = _parola_numero_it(sinistra) if sinistra else 1
            ds = _parola_numero_it(destra) if destra else 0
            if ls is not None and ds is not None:
                return ls * 1000 + ds

    if "cento" in w:
        sinistra, destra = w.split("cento", 1)
        ls = _parola_numero_it(sinistra) if sinistra else 1
        ds = _parola_numero_it(destra) if destra else 0
        if ls is not None and ds is not None:
            return ls * 100 + ds

    return None


def _parola_numero_en(w):
    """Integer value of ONE English number-word, or None. English does not
    concatenate, so a plain dictionary lookup is enough."""
    return _ATOMI_EN.get(w)


# Select the active tables for this build's language.
if _LANG == "en":
    _PUNTEGGIATURA = _PUNCT_EN
    _parola_numero = _parola_numero_en
else:
    _PUNTEGGIATURA = _PUNCT_IT
    _parola_numero = _parola_numero_it

# Longest punctuation phrase in words (for the greedy match).
_MAX_FRASE = max(len(f.split()) for f in _PUNTEGGIATURA)


def _consuma_numero(valori):
    """Consume the LONGEST prefix of `valori` that forms ONE single number.
    Returns (value, n_consumed).

    A new number begins (we stop) when a token would re-fill a place that is
    already taken: e.g. [23, 54] -> stop after 23, so '23 54' stays two
    numbers instead of being summed into 77. Bare multipliers (100/1000/
    1000000) scale the accumulator instead of being added."""
    totale = 0
    corrente = 0
    prec = None      # last additive atom (for the descending-magnitude check)
    count = 0
    for v in valori:
        if v == 100:
            corrente = (corrente or 1) * 100
            prec = None
            count += 1
            continue
        if v in (1000, 1000000):
            totale += (corrente or 1) * v
            corrente = 0
            prec = None
            count += 1
            continue
        # additive atom: valid only while magnitudes keep descending.
        if prec is not None and v >= prec:
            break        # a new number starts here
        corrente += v
        prec = v
        count += 1
    return totale + corrente, count


def _leggi_numero(tokens, i):
    """From position i, read the tokens that form the FIRST number.
    Returns (value, n_tokens). (None, 0) if tokens[i] is not a number."""
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
    valore, count = _consuma_numero(valori)
    if count == 0:
        return None, 0
    return valore, count


# ---------------------------------------------------------------------------
# Final assembly.
# ---------------------------------------------------------------------------
def _unisci(items):
    """Concatenate the items (text, space_before, space_after), inserting a
    space between two items only when BOTH adjacent sides allow it."""
    parti = []
    prec_dopo = False  # no leading space
    for testo, sp_prima, sp_dopo in items:
        if parti and prec_dopo and sp_prima:
            parti.append(" ")
        parti.append(testo)
        prec_dopo = sp_dopo
    return "".join(parti)


def trasforma(testo, numeri=True, punteggiatura=True, tabella=None):
    """Convert a phrase recognized by Vosk, applying punctuation and numbers.
    Normal words are left untouched with standard spacing.

    The two features are toggled independently by the caller:
      - punteggiatura=False: punctuation command words ("punto", "comma", ...)
        are kept as plain words instead of becoming characters.
      - numeri=False: spoken number sequences ("venti tre") are kept as words
        instead of becoming digits ("23").

    `tabella` lets the caller pass a custom punctuation map (phrase -> (char,
    space_before, space_after)), e.g. one loaded from the user's config file. If
    None, the built-in table for this build's language is used.
    """
    if not testo:
        return testo
    tab = tabella if tabella is not None else _PUNTEGGIATURA
    max_frase = max((len(f.split()) for f in tab), default=1) if tab else 1
    tokens = testo.split()
    items = []
    i = 0
    n_tok = len(tokens)
    while i < n_tok:
        # 1) punctuation, greedy from the longest phrase.
        if punteggiatura and tab:
            trovato = False
            for n in range(min(max_frase, n_tok - i), 0, -1):
                frase = " ".join(tokens[i:i + n])
                regola = tab.get(frase)
                if regola is not None:
                    car, sp_prima, sp_dopo = regola
                    items.append((car, sp_prima, sp_dopo))
                    i += n
                    trovato = True
                    break
            if trovato:
                continue

        # 2) number: consume exactly one number (adjacent numbers stay split).
        if numeri:
            valore, consumati = _leggi_numero(tokens, i)
            if consumati > 0:
                items.append((str(valore), True, True))
                i += consumati
                continue

        # 3) plain word.
        items.append((tokens[i], True, True))
        i += 1

    return _unisci(items)
