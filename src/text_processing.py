# -*- coding: utf-8 -*-
"""
text_processing.py - Post-processing of the text recognized by Vosk.

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

Single entry point: transform_vosk_recognized_text(testo) -> str.
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
_ITALIAN_SMALL_NUMBERS_0_TO_19 = {
    "zero": 0, "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11,
    "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
    "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19,
}
_ITALIAN_TENS_NUMBERS = {
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


def _build_italian_number_word_atoms():
    """word->value table for 0..99, including the Italian concatenated forms
    ('ventuno', 'ventitre', 'trentotto')."""
    number_word_atoms = dict(_ITALIAN_SMALL_NUMBERS_0_TO_19)
    number_word_atoms.update(_ITALIAN_TENS_NUMBERS)
    for tens_word, tens_value in _ITALIAN_TENS_NUMBERS.items():
        for units_word, units_value in _ITALIAN_SMALL_NUMBERS_0_TO_19.items():
            if units_value == 0:
                continue
            # before uno(1)/otto(8) the tens word drops its final vowel:
            # 'venti'+'uno' -> 'ventuno', 'trenta'+'otto' -> 'trentotto'.
            word_prefix_before_units = tens_word[:-1] if units_value in (1, 8) else tens_word
            number_word_atoms[word_prefix_before_units + units_word] = tens_value + units_value
            if units_value == 3:  # 'ventitre' and also 'ventitré'
                number_word_atoms[word_prefix_before_units + "tré"] = tens_value + units_value
    return number_word_atoms


_ITALIAN_NUMBER_WORD_ATOMS = _build_italian_number_word_atoms()
_ITALIAN_NUMBER_WORD_ATOMS["un"] = 1  # only as an internal prefix (e.g. 'unmilione')

_ENGLISH_NUMBER_WORD_ATOMS = dict(_UNITS_EN)
_ENGLISH_NUMBER_WORD_ATOMS.update(_TENS_EN)
_ENGLISH_NUMBER_WORD_ATOMS.update({"hundred": 100, "thousand": 1000, "million": 1000000})

# Bare multipliers: when one of these is a standalone token it SCALES the
# number being built instead of being added to it.
_NUMBER_SCALE_MULTIPLIERS = (100, 1000, 1000000)


def _italian_word_to_number_value(number_word):
    """Integer value of ONE Italian number-word, or None if not one.
    Recurses over the multipliers (milioni/mila/mille/cento) so it handles
    both separate tokens ('due', 'cento') and concatenated ones
    ('duecentotrentaquattro')."""
    if not number_word:
        return None
    if number_word in _ITALIAN_NUMBER_WORD_ATOMS:
        return _ITALIAN_NUMBER_WORD_ATOMS[number_word]

    for multiplier_word in ("milioni", "milione"):
        if multiplier_word in number_word:
            left_word_part, right_word_part = number_word.split(multiplier_word, 1)
            left_part_numeric_value = _italian_word_to_number_value(left_word_part) if left_word_part else 1
            right_part_numeric_value = _italian_word_to_number_value(right_word_part) if right_word_part else 0
            if left_part_numeric_value is not None and right_part_numeric_value is not None:
                return left_part_numeric_value * 1000000 + right_part_numeric_value

    for multiplier_word in ("mila", "mille"):
        if multiplier_word in number_word:
            left_word_part, right_word_part = number_word.split(multiplier_word, 1)
            left_part_numeric_value = _italian_word_to_number_value(left_word_part) if left_word_part else 1
            right_part_numeric_value = _italian_word_to_number_value(right_word_part) if right_word_part else 0
            if left_part_numeric_value is not None and right_part_numeric_value is not None:
                return left_part_numeric_value * 1000 + right_part_numeric_value

    if "cento" in number_word:
        left_word_part, right_word_part = number_word.split("cento", 1)
        left_part_numeric_value = _italian_word_to_number_value(left_word_part) if left_word_part else 1
        right_part_numeric_value = _italian_word_to_number_value(right_word_part) if right_word_part else 0
        if left_part_numeric_value is not None and right_part_numeric_value is not None:
            return left_part_numeric_value * 100 + right_part_numeric_value

    return None


def _english_word_to_number_value(number_word):
    """Integer value of ONE English number-word, or None. English does not
    concatenate, so a plain dictionary lookup is enough."""
    return _ENGLISH_NUMBER_WORD_ATOMS.get(number_word)


# Select the active tables for this build's language.
if _LANG == "en":
    _ACTIVE_PUNCTUATION_TABLE = _PUNCT_EN
    _word_to_number_value = _english_word_to_number_value
else:
    _ACTIVE_PUNCTUATION_TABLE = _PUNCT_IT
    _word_to_number_value = _italian_word_to_number_value

# Longest punctuation phrase in words (for the greedy match).
_MAX_PUNCTUATION_PHRASE_WORD_COUNT = max(len(f.split()) for f in _ACTIVE_PUNCTUATION_TABLE)


def _consume_number_from_value_list(numeric_values_list):
    """Consume the LONGEST prefix of `numeric_values_list` that forms ONE single number.
    Returns (value, n_consumed).

    A new number begins (we stop) when a token would re-fill a place that is
    already taken: e.g. [23, 54] -> stop after 23, so '23 54' stays two
    numbers instead of being summed into 77. Bare multipliers (100/1000/
    1000000) scale the accumulator instead of being added."""
    total_accumulated_value = 0
    current_partial_number = 0
    previous_additive_atom_value = None
    count = 0
    for current_numeric_value in numeric_values_list:
        if current_numeric_value == 100:
            current_partial_number = (current_partial_number or 1) * 100
            previous_additive_atom_value = None
            count += 1
            continue
        if current_numeric_value in (1000, 1000000):
            total_accumulated_value += (current_partial_number or 1) * current_numeric_value
            current_partial_number = 0
            previous_additive_atom_value = None
            count += 1
            continue
        # additive atom: valid only while magnitudes keep descending.
        if previous_additive_atom_value is not None and current_numeric_value >= previous_additive_atom_value:
            break        # a new number starts here
        current_partial_number += current_numeric_value
        previous_additive_atom_value = current_numeric_value
        count += 1
    return total_accumulated_value + current_partial_number, count


def _read_number_from_tokens(tokens, i):
    """From position i, read the tokens that form the FIRST number.
    Returns (value, n_tokens). (None, 0) if tokens[i] is not a number."""
    word_numeric_values = []
    j = i
    while j < len(tokens):
        v = _word_to_number_value(tokens[j])
        if v is None:
            break
        word_numeric_values.append(v)
        j += 1
    if not word_numeric_values:
        return None, 0
    parsed_number_value, count = _consume_number_from_value_list(word_numeric_values)
    if count == 0:
        return None, 0
    return parsed_number_value, count


# ---------------------------------------------------------------------------
# Final assembly.
# ---------------------------------------------------------------------------
def _join_processed_text_items(items):
    """Concatenate the items (text, space_before, space_after), inserting a
    space between two items only when BOTH adjacent sides allow it."""
    assembled_text_parts = []
    previous_item_allows_trailing_space = False  # no leading space
    for item_text, allows_space_before, allows_space_after in items:
        if assembled_text_parts and previous_item_allows_trailing_space and allows_space_before:
            assembled_text_parts.append(" ")
        assembled_text_parts.append(item_text)
        previous_item_allows_trailing_space = allows_space_after
    return "".join(assembled_text_parts)


def transform_vosk_recognized_text(raw_vosk_text, convert_numbers_to_digits=True, convert_punctuation_words=True, custom_punctuation_table=None):
    """Convert a phrase recognized by Vosk, applying punctuation and numbers.
    Normal words are left untouched with standard spacing.

    The two features are toggled independently by the caller:
      - convert_punctuation_words=False: punctuation command words ("punto", "comma", ...)
        are kept as plain words instead of becoming characters.
      - convert_numbers_to_digits=False: spoken number sequences ("venti tre") are kept as words
        instead of becoming digits ("23").

    `custom_punctuation_table` lets the caller pass a custom punctuation map (phrase -> (char,
    space_before, space_after)), e.g. one loaded from the user's config file. If
    None, the built-in table for this build's language is used.
    """
    if not raw_vosk_text:
        return raw_vosk_text
    active_punctuation_table = custom_punctuation_table if custom_punctuation_table is not None else _ACTIVE_PUNCTUATION_TABLE
    max_punctuation_phrase_word_count = max((len(f.split()) for f in active_punctuation_table), default=1) if active_punctuation_table else 1
    tokens = raw_vosk_text.split()
    processed_items = []
    i = 0
    total_token_count = len(tokens)
    while i < total_token_count:
        # 1) punctuation, greedy from the longest phrase.
        if convert_punctuation_words and active_punctuation_table:
            punctuation_match_found = False
            for n in range(min(max_punctuation_phrase_word_count, total_token_count - i), 0, -1):
                candidate_phrase = " ".join(tokens[i:i + n])
                punctuation_rule = active_punctuation_table.get(candidate_phrase)
                if punctuation_rule is not None:
                    punctuation_character, space_allowed_before_punct, space_allowed_after_punct = punctuation_rule
                    processed_items.append((punctuation_character, space_allowed_before_punct, space_allowed_after_punct))
                    i += n
                    punctuation_match_found = True
                    break
            if punctuation_match_found:
                continue

        # 2) number: consume exactly one number (adjacent numbers stay split).
        if convert_numbers_to_digits:
            number_value, tokens_consumed_count = _read_number_from_tokens(tokens, i)
            if tokens_consumed_count > 0:
                processed_items.append((str(number_value), True, True))
                i += tokens_consumed_count
                continue

        # 3) plain word.
        processed_items.append((tokens[i], True, True))
        i += 1

    return _join_processed_text_items(processed_items)
