# -*- coding: utf-8 -*-
"""
dictation.py - UNO component (ProtocolHandler) for offline voice dictation
               in LibreOffice Writer using Vosk.

Flow:
    1. Toolbar button click (Addons.xcu) -> URL "vnd.libreitalia.dettatura:toggle".
    2. ProtocolHandler.xcu routes the URL to this component.
    3. dispatch() starts/stops an audio listening thread.
    4. The thread recognizes speech with Vosk and inserts text at the cursor.

Visual feedback:
    The button is a toggle: when dictation is active LibreOffice shows it
    as PRESSED/highlighted. The state is notified to the XStatusListeners of
    the toolbar via FeatureStateEvent.State (True = listening).

Diagnostics:
    All events are logged to <tmp>/voice-dictation-logs/voice_dictation_<lang>.log
    (one file per language, shared folder), so it is possible to tell if the
    component is loaded and if clicks are arriving. The file is reset beyond ~4 MB.
    Next to it sits the per-language config voice_dictation_<lang>.cfg.json with the
    numbers/punctuation toggle flags and verbose/debug (info/error popups).
"""

import os
import sys
import json
import queue
import tempfile
import threading
import traceback
import datetime

import uno
import unohelper

# ---------------------------------------------------------------------------
# Bundled dependencies take priority over system packages.
# LibreOffice appends <oxt>/pythonpath to the END of sys.path, so a broken
# system package (e.g. a bad tqdm in /usr/lib/.../site-packages) could be
# picked up instead of ours. By inserting at the HEAD, our self-consistent
# bundle always wins.
_PYTHONPATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pythonpath")
if os.path.isdir(_PYTHONPATH) and sys.path[0:1] != [_PYTHONPATH]:
    sys.path.insert(0, _PYTHONPATH)

# The component directory is not guaranteed to be in sys.path under the UNO
# loader: insert it so sibling modules (text_processing.py) can be imported.
_SELFDIR = os.path.dirname(os.path.abspath(__file__))
if _SELFDIR not in sys.path:
    sys.path.insert(0, _SELFDIR)

from com.sun.star.frame import XDispatchProvider, XDispatch
from com.sun.star.lang import XServiceInfo, XInitialization

# Text post-processing (punctuation + numbers). Loaded ROBUSTLY via explicit
# file path instead of "import text_processing".
#
# LibreOffice uses ONE single Python interpreter for the entire soffice process
# (quickstarter included), shared across extensions and sessions. A named import
# stays in sys.modules for the lifetime of the process: after an extension update
# WITHOUT a full LibreOffice restart it would keep returning the OLD module
# (symptom: "same behaviour as N versions ago"). Also, both the it/en extensions
# ship a module named "text_processing": the first one loaded would win. By
# loading the physical file next to us via importlib (with a unique per-language
# name and without relying on the sys.modules cache) we ALWAYS execute the
# freshly installed copy, with no name collisions and no stale cache.
try:
    import importlib.util as _import_util
    _text_processing_source_file_path = os.path.join(_SELFDIR, "text_processing.py")
    _text_processing_module_spec = _import_util.spec_from_file_location("text_processing_@LANG@", _text_processing_source_file_path)
    text_transformation_module = _import_util.module_from_spec(_text_processing_module_spec)
    _text_processing_module_spec.loader.exec_module(text_transformation_module)
except Exception:
    text_transformation_module = None

# ---------------------------------------------------------------------------
# Registration constants. Must match ProtocolHandler.xcu.
# ---------------------------------------------------------------------------
IMPL_NAME = "org.libreitalia.dettaturavocale.ProtocolHandler"
SERVICE_NAMES = ("com.sun.star.frame.ProtocolHandler",)
PROTOCOL = "vnd.libreitalia.dettatura:"
EXTENSION_ID = "org.libreitalia.dettaturavocale"

# Language code for THIS build (injected by _pack.py via the @LANG@ token).
# Used for the log filename and toggle persistence. In dev/src it stays
# "@LANG@" and falls back to "it".
LANG = "@LANG@"
if LANG not in ("it", "en"):
    LANG = "it"

# Audio parameters required by Vosk models (mono, 16 kHz, 16-bit PCM).
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

# Log folder SHARED between language variants, one file per language
# ("voice_dictation_it.log", "voice_dictation_en.log"). Open manually
# (no menu entry: with it+en installed LibreOffice does not deduplicate
# same-named add-on menu entries).
LOG_DIR = os.path.join(tempfile.gettempdir(), "voice-dictation-logs")
LOG_PATH = os.path.join(LOG_DIR, "voice_dictation_%s.log" % LANG)
# Persisted state (toggles + verbose/debug), per-language, next to the logs.
CONFIG_PATH = os.path.join(LOG_DIR, "voice_dictation_%s.cfg.json" % LANG)
# Log size cap: beyond this threshold the file is cleared (prevents unbounded
# growth). ~4 MB.
LOG_MAX_BYTES = 4 * 1024 * 1024


# ---------------------------------------------------------------------------
# Voice command tables (formatting / lists / case / undo). These are spoken
# command phrases recognized by Vosk: they arrive inside the recognized text,
# NOT as toolbar clicks. Each phrase maps to an internal action code executed
# by the handler. Like the punctuation table, this is language-specific and the
# matching is greedy (longest phrase first) over the raw lowercase Vosk tokens,
# BEFORE punctuation/number transformation.
#
# Action codes:
#   TOGGLE_BULLET_LIST / TOGGLE_NUMBER_LIST  toggle un/ordered list on the para
#   TERMINATE_LIST                           drop list formatting (plain text)
#   BOLD_ON/OFF, ITALIC_ON/OFF, UNDERLINE_ON/OFF   character run formatting
#   NEXT_CAPITAL    capitalize ONLY the first letter of the next dictated word
#   CAPSLOCK_ON/OFF voice caps lock: everything UPPERCASE until turned off
#   UNDO_LAST       undo the last inserted block (.uno:Undo)
#   REDO_LAST       redo the last undone action (.uno:Redo)
#   RESET_FORMAT    clear bold/italic/underline and any active case state
#   PAGE_BREAK      insert a page break (.uno:InsertPagebreak)
#   ALIGN_LEFT/CENTER/RIGHT/JUSTIFY   paragraph alignment (.uno:*Para)
#   PRINT           open the print dialog (.uno:Print)
#   FONT_UP/FONT_DOWN   grow/shrink the size of the next dictated text. An
#     optional trailing spoken number sets the amount in points
#     ("aumenta font cinque" -> +5); with no number a default step is used.
#   DATE_TODAY      insert today's date, computed at execution time so it is
#     always the current day (dd/mm/yyyy for it, mm/dd/yyyy for en).
# ---------------------------------------------------------------------------
_COMMANDS_ITALIAN = {
    "elenco puntato":         "TOGGLE_BULLET_LIST",
    "elenco numerato":        "TOGGLE_NUMBER_LIST",
    "fine elenco":            "TERMINATE_LIST",
    "attiva grassetto":       "BOLD_ON",
    "tutto grassetto":        "BOLD_ON",
    "disattiva grassetto":    "BOLD_OFF",
    "fine grassetto":         "BOLD_OFF",
    "attiva corsivo":         "ITALIC_ON",
    "tutto corsivo":          "ITALIC_ON",
    "disattiva corsivo":      "ITALIC_OFF",
    "fine corsivo":           "ITALIC_OFF",
    "attiva sottolineato":    "UNDERLINE_ON",
    "disattiva sottolineato": "UNDERLINE_OFF",
    "tutto maiuscolo":        "CAPSLOCK_ON",
    "fine maiuscolo":         "CAPSLOCK_OFF",
    "maiuscolo":              "NEXT_CAPITAL",
    "cancella ultimo":        "UNDO_LAST",
    "rifai":                  "REDO_LAST",
    "ripristina":             "REDO_LAST",
    "testo normale":          "RESET_FORMAT",
    "interruzione pagina":    "PAGE_BREAK",
    "salto pagina":           "PAGE_BREAK",
    "allinea sinistra":       "ALIGN_LEFT",
    "allinea centro":         "ALIGN_CENTER",
    "allinea destra":         "ALIGN_RIGHT",
    "giustifica":             "ALIGN_JUSTIFY",
    "giustificato":           "ALIGN_JUSTIFY",
    "stampa":                 "PRINT",
    "aumenta font":           "FONT_UP",
    "ingrandisci font":       "FONT_UP",
    "diminuisci font":        "FONT_DOWN",
    "riduci font":            "FONT_DOWN",
    "ritorna data":           "DATE_TODAY",
    "inserisci data":         "DATE_TODAY",
    "data odierna":           "DATE_TODAY",
}

_COMMANDS_ENGLISH = {
    "bullet list":      "TOGGLE_BULLET_LIST",
    "bulleted list":    "TOGGLE_BULLET_LIST",
    "numbered list":    "TOGGLE_NUMBER_LIST",
    "end list":         "TERMINATE_LIST",
    "bold on":          "BOLD_ON",
    "start bold":       "BOLD_ON",
    "bold off":         "BOLD_OFF",
    "end bold":         "BOLD_OFF",
    "italic on":        "ITALIC_ON",
    "start italic":     "ITALIC_ON",
    "italic off":       "ITALIC_OFF",
    "end italic":       "ITALIC_OFF",
    "underline on":     "UNDERLINE_ON",
    "underline off":    "UNDERLINE_OFF",
    "all caps":         "CAPSLOCK_ON",
    "caps on":          "CAPSLOCK_ON",
    "caps off":         "CAPSLOCK_OFF",
    "end caps":         "CAPSLOCK_OFF",
    "capitalize":       "NEXT_CAPITAL",
    "capital":          "NEXT_CAPITAL",
    "delete last":      "UNDO_LAST",
    "scratch that":     "UNDO_LAST",
    "redo":             "REDO_LAST",
    "normal text":      "RESET_FORMAT",
    "page break":       "PAGE_BREAK",
    "insert page break": "PAGE_BREAK",
    "align left":       "ALIGN_LEFT",
    "align center":     "ALIGN_CENTER",
    "align right":      "ALIGN_RIGHT",
    "justify":          "ALIGN_JUSTIFY",
    "justified":        "ALIGN_JUSTIFY",
    "print":            "PRINT",
    "increase font":    "FONT_UP",
    "bigger font":      "FONT_UP",
    "decrease font":    "FONT_DOWN",
    "smaller font":     "FONT_DOWN",
    "return date":      "DATE_TODAY",
    "insert date":      "DATE_TODAY",
    "current date":     "DATE_TODAY",
}

if LANG == "en":
    _ACTIVE_COMMAND_TABLE = _COMMANDS_ENGLISH
else:
    _ACTIVE_COMMAND_TABLE = _COMMANDS_ITALIAN
# Longest command phrase in words (for the greedy match).
_MAX_COMMAND_PHRASE_WORD_COUNT = max(len(f.split()) for f in _ACTIVE_COMMAND_TABLE)

# Default font step (points) for FONT_UP/FONT_DOWN when no number is spoken.
FONT_STEP_DEFAULT = 4


def _split_text_into_command_segments(raw_recognized_text, cmd_map, max_phrase_word_count):
    """Split raw Vosk text into ordered segments, preserving the order in which
    commands and dictated words were spoken inside a single utterance.

    `cmd_map` is the active phrase->code table (loaded from config) and
    `max_phrase_word_count` its longest phrase in words.

    Returns a list of (kind, payload):
      ("CMD",  action_code)   a recognized command phrase. For FONT_UP/FONT_DOWN
                              an amount may be appended as "FONT_UP:5".
      ("TEXT", "raw words")   a run of plain words to dictate

    Matching is greedy from the longest phrase, so "tutto maiuscolo" wins over
    "maiuscolo" and "fine grassetto" is not split into words. Non-command tokens
    accumulate into TEXT runs."""
    tokens = raw_recognized_text.split()
    segments = []
    pending_words_buffer = []
    i = 0
    n = len(tokens)
    while i < n:
        match_found = False
        for k in range(min(max_phrase_word_count, n - i), 0, -1):
            candidate_phrase = " ".join(tokens[i:i + k])
            code = cmd_map.get(candidate_phrase)
            if code is not None:
                if pending_words_buffer:
                    segments.append(("TEXT", " ".join(pending_words_buffer)))
                    pending_words_buffer = []
                tokens_consumed = k
                # Font commands may take a trailing spoken number as argument
                # ("aumenta font cinque"): consume it and attach as "CODE:N".
                if code in ("FONT_UP", "FONT_DOWN") and text_transformation_module is not None:
                    try:
                        spoken_number_value, spoken_number_token_count = text_transformation_module._read_number_from_tokens(tokens, i + k)
                    except Exception:
                        spoken_number_value, spoken_number_token_count = None, 0
                    if spoken_number_value is not None and spoken_number_token_count > 0:
                        code = "%s:%d" % (code, spoken_number_value)
                        tokens_consumed += spoken_number_token_count
                segments.append(("CMD", code))
                i += tokens_consumed
                match_found = True
                break
        if not match_found:
            pending_words_buffer.append(tokens[i])
            i += 1
    if pending_words_buffer:
        segments.append(("TEXT", " ".join(pending_words_buffer)))
    return segments


def log(msg):
    """Write a timestamped line to the log file (best-effort).
    If the file exceeds LOG_MAX_BYTES it is cleared before writing."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        try:
            if os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
                open(LOG_PATH, "w").close()
        except OSError:
            pass  # file does not exist yet
        timestamp_string = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (timestamp_string, msg))
    except Exception:
        pass


# Traces the simple act of loading this module: if this line does not appear
# in the log, the Python component is not being loaded by LibreOffice at all.
log("=== modulo dictation.py caricato (pid %s) ===" % os.getpid())


# ---------------------------------------------------------------------------
# Mutual exclusion between language variants (it, en, ...).
# Multiple variants can coexist INSTALLED, but MUST NOT listen to the
# microphone at the same time. We use a FIXED-NAME lockfile (not per-language)
# so the IT extension "sees" the EN lock and vice versa. It holds the PID
# and extension identifier of the owner.
# ---------------------------------------------------------------------------
LOCK_PATH = os.path.join(tempfile.gettempdir(), "voice-dictation.lock")


def _is_process_alive(pid):
    """Returns True if the process with this PID is still running."""
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        # On Windows os.kill(pid, 0) can TERMINATE the process: avoid it.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            process_handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if process_handle:
                ctypes.windll.kernel32.CloseHandle(process_handle)
                return True
            return False
        except Exception:
            return True  # when in doubt, treat as alive (don't steal the lock)
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        import errno
        return e.errno == errno.EPERM  # process exists but we lack permission


def _read_lock_file_contents():
    """Returns (pid, identifier) from the lock file, or (None, None) if absent/unreadable."""
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            pid = int(f.readline().strip())
            ident = f.readline().strip()
        return pid, ident
    except Exception:
        return None, None


def _acquire_dictation_lock():
    """Tries to acquire the lock. Returns False if another LIVE instance holds it."""
    try:
        if os.path.exists(LOCK_PATH):
            pid, ident = _read_lock_file_contents()
            if pid and _is_process_alive(pid):
                # Busy, unless it is ourselves (same pid+identifier).
                if not (pid == os.getpid() and ident == EXTENSION_ID):
                    log("lock occupato da pid=%s ident=%s" % (pid, ident))
                    return False
            # Otherwise the lock is stale (dead process): overwrite it.
        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            f.write("%d\n%s\n" % (os.getpid(), EXTENSION_ID))
        return True
    except Exception:
        log("lock: errore acquisizione:\n" + traceback.format_exc())
        return True  # don't block usage due to an I/O error


def _release_dictation_lock():
    """Removes the lock only if it is ours (same pid+identifier). Idempotent."""
    try:
        if not os.path.exists(LOCK_PATH):
            return
        pid, ident = _read_lock_file_contents()
        if pid == os.getpid() and ident == EXTENSION_ID:
            os.remove(LOCK_PATH)
    except Exception:
        log("lock: errore rilascio:\n" + traceback.format_exc())


def _stub_optional_python_dependencies():
    """Neutralize optional dependencies that break under the UNO loader.

    vosk imports tqdm, which does:
        try: from envwrap import envwrap
        except ModuleNotFoundError: pass
    However LibreOffice's import hook (uno.py) raises ImportError (the base
    class) instead of ModuleNotFoundError, so tqdm's guard does not trigger
    and the import explodes. We register an 'envwrap' stub in sys.modules so
    the import always succeeds. tqdm is not needed: vosk uses it only for the
    model download progress bar (which we bundle already)."""
    import types as _types
    if "envwrap" not in sys.modules:
        m = _types.ModuleType("envwrap")

        def envwrap(prefix, types=None, is_method=False, **_kw):
            # Identity decorator: leaves the function unchanged.
            def deco(fn):
                return fn
            return deco

        m.envwrap = envwrap
        sys.modules["envwrap"] = m
        log("stub envwrap registrato")


def _log_environment_diagnostics():
    """Log information useful for diagnosing native library loading issues (mainly Windows)."""
    try:
        log("--- DIAGNOSTICA ---")
        log("platform=%s machine=%s" % (sys.platform, getattr(os, "uname", lambda: "?")() if hasattr(os, "uname") else "?"))
        log("python=%s" % sys.version.replace("\n", " "))
        log("pythonpath bundle=%s" % _PYTHONPATH)
        if os.path.isdir(_PYTHONPATH):
            directory_contents = sorted(os.listdir(_PYTHONPATH))
            cffi_backend_filenames = [v for v in directory_contents if v.startswith("_cffi_backend")]
            log("_cffi_backend presenti: %s" % cffi_backend_filenames)
            log("_sounddevice_data presente: %s" % os.path.isdir(os.path.join(_PYTHONPATH, "_sounddevice_data")))
            voskdir = os.path.join(_PYTHONPATH, "vosk")
            if os.path.isdir(voskdir):
                native = [v for v in os.listdir(voskdir) if v.lower().endswith((".dll", ".so", ".dylib"))]
                log("native in vosk/: %s" % native)
        # On Windows, dependent DLLs (libvosk -> libstdc++/libgcc/winpthread)
        # must be findable: add their folders to the DLL search path.
        if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
            for sub in ("", "vosk"):
                d = os.path.join(_PYTHONPATH, sub) if sub else _PYTHONPATH
                if os.path.isdir(d):
                    try:
                        os.add_dll_directory(d)
                        log("add_dll_directory: %s" % d)
                    except Exception:
                        log("add_dll_directory fallita per %s" % d)
        log("--- FINE DIAGNOSTICA ---")
    except Exception:
        log("diagnostica fallita:\n" + traceback.format_exc())


# ===========================================================================
# Recognition engine: Vosk + audio capture in its own thread.
# ===========================================================================
class DictationEngine:
    """Manages audio listening and speech recognition in a separate thread.

    Decoupled from UNO: recognized text is passed to the callback
    `insert_recognized_text_callback`. When the thread ends (stop or error)
    it calls `on_stop` so the caller can update the button state.
    """

    def __init__(self, model_path, insert_recognized_text_callback, on_stop=None):
        self._model_path = model_path
        self._insert_recognized_text_callback = insert_recognized_text_callback
        self._on_stop = on_stop

        self._thread = None
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()

    @property
    def is_listening(self):
        return self._thread is not None and self._thread.is_alive()

    def start_listening(self):
        if self.is_listening:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._audio_recognition_loop, name="DettaturaVosk", daemon=True)
        self._thread.start()

    def stop_listening(self):
        # No join(): we are on the UI thread and must not block it.
        self._stop_event.set()
        self._thread = None

    # --- Worker thread execution ------------------------------------------
    def _audio_stream_callback(self, indata, frames, time_info, status):
        if status:
            log("audio status: %s" % status)
        self._audio_queue.put(bytes(indata))

    def _audio_recognition_loop(self):
        try:
            log("thread dettatura: avvio")
            _log_environment_diagnostics()
            _stub_optional_python_dependencies()

            # Separate imports: if one fails, the log says EXACTLY which one.
            try:
                from vosk import Model, KaldiRecognizer
                log("import vosk OK")
            except Exception:
                log("ERRORE import vosk:\n" + traceback.format_exc())
                raise
            try:
                import sounddevice as sd
                log("import sounddevice OK")
            except Exception:
                log("ERRORE import sounddevice (PortAudio?):\n" + traceback.format_exc())
                raise
            try:
                log("device audio: %s" % repr(sd.query_devices()))
                log("default input: %s" % repr(sd.default.device))
            except Exception:
                log("query device fallita (microfono?):\n" + traceback.format_exc())

            if not os.path.isdir(self._model_path):
                log("ERRORE: modello Vosk non trovato in: %s" % self._model_path)
                return

            model = Model(self._model_path)
            recognizer = KaldiRecognizer(model, SAMPLE_RATE)
            recognizer.SetWords(False)
            log("modello caricato, apro stream audio")

            import array
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                   dtype="int16", channels=1,
                                   callback=self._audio_stream_callback):
                log("ascolto avviato")
                audio_blocks_processed_count = 0
                max_audio_level_seen = 0
                while not self._stop_event.is_set():
                    try:
                        data = self._audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    audio_blocks_processed_count += 1
                    # Instrumentation: every ~25 blocks log audio level + Vosk partial.
                    if audio_blocks_processed_count % 25 == 1:
                        try:
                            audio_samples_array = array.array("h")
                            audio_samples_array.frombytes(data)
                            current_block_audio_level = max((abs(x) for x in audio_samples_array), default=0)
                            max_audio_level_seen = max(max_audio_level_seen, current_block_audio_level)
                            partial_recognition_text = json.loads(recognizer.PartialResult()).get("partial", "")
                            log("blocco=%d livello=%d parziale=%r" % (audio_blocks_processed_count, current_block_audio_level, partial_recognition_text))
                        except Exception:
                            log("instrum. fallita:\n" + traceback.format_exc())
                    if recognizer.AcceptWaveform(data):
                        recognized_text = json.loads(recognizer.Result()).get("text", "")
                        if recognized_text:
                            log("riconosciuto: %r" % recognized_text)
                            self._insert_recognized_text_callback(recognized_text)

                final_recognition_text = json.loads(recognizer.FinalResult()).get("text", "")
                log("fine ascolto: blocchi=%d livello_max=%d finale=%r"
                    % (audio_blocks_processed_count, max_audio_level_seen, final_recognition_text))
                if final_recognition_text:
                    self._insert_recognized_text_callback(final_recognition_text)
            log("ascolto fermato")

        except Exception:
            log("ECCEZIONE nel thread dettatura:\n" + traceback.format_exc())
        finally:
            if self._on_stop:
                try:
                    self._on_stop()
                except Exception:
                    log("on_stop fallito:\n" + traceback.format_exc())


# ===========================================================================
# UNO component: receives clicks, drives the engine, updates button state.
# ===========================================================================
class DictationHandler(unohelper.Base, XServiceInfo, XDispatchProvider,
                       XDispatch, XInitialization):

    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None
        self.dictation_engine = None
        # Toolbar listeners (to highlight the button when active).
        self._toolbar_status_listeners = []   # list of (XStatusListener, URL)
        # State persisted for THIS language (independent config file):
        #   numbers/punctuation -> recognition toggle (default ON)
        #   verbose -> show informational popups (toggle confirmation); default OFF
        #   debug   -> show error popups; default ON
        #   verbose-logging -> log every executed voice command + state change
        #     (diagnostic for the command layer); default OFF, zero overhead off.
        self._numbers_conversion_enabled = True
        self._punctuation_conversion_enabled = True
        self._voice_commands_enabled = True
        self._verbose_info_popups_enabled = False
        self._debug_error_popups_enabled = True
        self._verbose_command_logging_enabled = False
        # Active phrase tables (loaded from config, so the user can edit them).
        # Default to the built-in tables; _load_config_from_file overrides if present.
        self._active_voice_command_map = dict(_ACTIVE_COMMAND_TABLE)
        self._active_punctuation_map = self._get_builtin_punctuation_table()
        self._max_command_phrase_word_count = _MAX_COMMAND_PHRASE_WORD_COUNT
        # Transient formatting state for the voice commands. Per session, NOT
        # persisted: bold/italic/underline runs, voice caps lock, the one-shot
        # "capitalize next word" flag, and an absolute font height (None = use
        # the document default).
        self._bold_formatting_active = False
        self._italic_formatting_active = False
        self._underline_formatting_active = False
        self._caps_lock_voice_active = False
        self._capitalize_next_word_flag = False
        self._override_font_height_points = None
        self._load_config_from_file()
        # Write the config file with defaults if it does not exist yet, or if
        # a pre-existing config is missing the editable dictionaries
        # (comandi_map/punteggiatura_map): this ensures the user always has a
        # complete file to edit (toggles + verbose/debug/verbose-logging + maps).
        if not os.path.exists(CONFIG_PATH) or self._config_needs_update:
            self._save_config_to_file()
        log("DettaturaHandler creato (numeri=%s punteggiatura=%s comandi=%s verbose=%s debug=%s verbose-logging=%s)"
            % (self._numbers_conversion_enabled, self._punctuation_conversion_enabled, self._voice_commands_enabled,
               self._verbose_info_popups_enabled, self._debug_error_popups_enabled, self._verbose_command_logging_enabled))

    # --- XInitialization ---------------------------------------------------
    def initialize(self, args):
        if args:
            self.frame = args[0]
        log("initialize: frame=%s" % (self.frame is not None))

    # --- XServiceInfo ------------------------------------------------------
    def getImplementationName(self):
        return IMPL_NAME

    def supportsService(self, name):
        return name in SERVICE_NAMES

    def getSupportedServiceNames(self):
        return SERVICE_NAMES

    # --- XDispatchProvider -------------------------------------------------
    def queryDispatch(self, url, target_frame_name, search_flags):
        if url.Complete.startswith(PROTOCOL):
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags)
                     for r in requests)

    # --- XDispatch ---------------------------------------------------------
    def dispatch(self, url, args):
        log("dispatch: %s" % url.Complete)
        full_command_url = url.Complete
        if not full_command_url.startswith(PROTOCOL):
            return
        # The action is the part after the protocol prefix: toggle | togglenumbers |
        # togglepunct | togglecommands.
        action_name = full_command_url[len(PROTOCOL):]
        try:
            if action_name == "togglenumbers":
                self._toggle_numbers_conversion()
            elif action_name == "togglepunct":
                self._toggle_punctuation_conversion()
            elif action_name == "togglecommands":
                self._toggle_voice_commands()
            else:  # "toggle"
                self._toggle()
        except Exception:
            error_traceback_text = traceback.format_exc()
            log("ECCEZIONE in dispatch:\n" + error_traceback_text)
            self._show_error_message_popup("Errore:\n" + error_traceback_text)

    def addStatusListener(self, listener, url):
        # The toolbar registers a listener here to know the state of the command.
        self._toolbar_status_listeners.append((listener, url))
        # Immediately send the current state, specific to this command.
        self._notify_single_listener_state(listener, url, self._get_command_button_state_for_url(url.Complete))

    def removeStatusListener(self, listener, url):
        self._toolbar_status_listeners = [(l, u) for (l, u) in self._toolbar_status_listeners if l != listener]

    # --- Application logic -------------------------------------------------
    def _check_if_listening(self):
        return self.dictation_engine is not None and self.dictation_engine.is_listening

    def _ensure_engine_exists(self):
        if self.dictation_engine is None:
            self.dictation_engine = DictationEngine(
                model_path=self._get_vosk_model_directory_path(),
                insert_recognized_text_callback=self._insert_dictated_text_at_cursor,
                on_stop=self._on_engine_stopped,
            )

    def _start_dictation(self):
        self._ensure_engine_exists()
        if self.dictation_engine.is_listening:
            return
        # Mutual exclusion: do not start if another language/window is already listening.
        if not _acquire_dictation_lock():
            self._show_error_message_popup(
                "Dettatura gia' attiva (un'altra lingua o finestra).\n"
                "Fermala prima di iniziare qui.")
            log("START rifiutato: lock occupato")
            return
        # Re-read the config so edits to the toggles or the command/punctuation
        # maps take effect on the next dictation without restarting LibreOffice.
        self._load_config_from_file()
        # Fresh session: clear any leftover formatting/case state so a new
        # dictation never inherits bold/caps/font from a previous run.
        self._bold_formatting_active = self._italic_formatting_active = self._underline_formatting_active = False
        self._caps_lock_voice_active = self._capitalize_next_word_flag = False
        self._override_font_height_points = None
        log("START (modello: %s)" % self._get_vosk_model_directory_path())
        self.dictation_engine.start_listening()
        self._update_microphone_button_icon(True)
        self._broadcast_all_listener_states()

    def _stop_dictation(self):
        if self.dictation_engine is not None and self.dictation_engine.is_listening:
            log("STOP")
            self.dictation_engine.stop_listening()
            _release_dictation_lock()
        self._update_microphone_button_icon(False)
        self._broadcast_all_listener_states()

    def _toggle(self):
        self._ensure_engine_exists()
        if self.dictation_engine.is_listening:
            self._stop_dictation()
        else:
            self._start_dictation()

    # --- Independent toggles: numbers and punctuation ---------------------
    def _toggle_numbers_conversion(self):
        self._numbers_conversion_enabled = not self._numbers_conversion_enabled
        log("toggle numeri -> %s" % self._numbers_conversion_enabled)
        self._save_config_to_file()
        self._broadcast_all_listener_states()
        if LANG == "en":
            self._show_info_message_popup("Numbers: %s" % ("ON" if self._numbers_conversion_enabled else "OFF"))
        else:
            self._show_info_message_popup("Numeri: %s" % ("ATTIVI" if self._numbers_conversion_enabled else "DISATTIVI"))

    def _toggle_punctuation_conversion(self):
        self._punctuation_conversion_enabled = not self._punctuation_conversion_enabled
        log("toggle punteggiatura -> %s" % self._punctuation_conversion_enabled)
        self._save_config_to_file()
        self._broadcast_all_listener_states()
        if LANG == "en":
            self._show_info_message_popup("Punctuation: %s" % ("ON" if self._punctuation_conversion_enabled else "OFF"))
        else:
            self._show_info_message_popup("Punteggiatura: %s"
                       % ("ATTIVA" if self._punctuation_conversion_enabled else "DISATTIVA"))

    def _toggle_voice_commands(self):
        self._voice_commands_enabled = not self._voice_commands_enabled
        log("toggle comandi -> %s" % self._voice_commands_enabled)
        self._save_config_to_file()
        self._broadcast_all_listener_states()
        if LANG == "en":
            self._show_info_message_popup("Formatting commands: %s"
                       % ("ON" if self._voice_commands_enabled else "OFF"))
        else:
            self._show_info_message_popup("Comandi formattazione: %s"
                       % ("ATTIVI" if self._voice_commands_enabled else "DISATTIVI"))

    def _get_builtin_punctuation_table(self):
        """Built-in punctuation table for this build's language (used as the
        default to materialize into the config)."""
        if text_transformation_module is None:
            return {}
        return dict(text_transformation_module._ACTIVE_PUNCTUATION_TABLE)

    def _apply_vosk_text_post_processing(self, raw_text_from_vosk):
        """Apply punctuation + numbers to the Vosk text according to the toggles,
        using the punctuation table loaded from config. On error (or missing module)
        returns the raw text unchanged."""
        if text_transformation_module is None:
            return raw_text_from_vosk
        try:
            return text_transformation_module.transform_vosk_recognized_text(
                raw_text_from_vosk,
                convert_numbers_to_digits=self._numbers_conversion_enabled,
                convert_punctuation_words=self._punctuation_conversion_enabled,
                custom_punctuation_table=self._active_punctuation_map)
        except Exception:
            log("text processing failed:\n" + traceback.format_exc())
            return raw_text_from_vosk

    # --- State persistence (toggles + verbose/debug + maps) ---------------
    def _load_config_from_file(self):
        # Set when a pre-existing config lacks the editable maps, so __init__
        # can rewrite a complete file.
        self._config_needs_update = False
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config_file_data = json.load(f)
            self._numbers_conversion_enabled = bool(config_file_data.get("numeri", True))
            self._punctuation_conversion_enabled = bool(config_file_data.get("punteggiatura", True))
            self._voice_commands_enabled = bool(config_file_data.get("comandi", True))
            self._verbose_info_popups_enabled = bool(config_file_data.get("verbose", False))
            self._debug_error_popups_enabled = bool(config_file_data.get("debug", True))
            self._verbose_command_logging_enabled = bool(config_file_data.get("verbose-logging", False))
            if "comandi_map" not in config_file_data or "punteggiatura_map" not in config_file_data:
                self._config_needs_update = True
            # User-editable command map (phrase -> action code). Fall back to the
            # built-in table when absent/invalid.
            loaded_command_map = config_file_data.get("comandi_map")
            if isinstance(loaded_command_map, dict) and loaded_command_map:
                self._active_voice_command_map = {str(k): str(v) for k, v in loaded_command_map.items()}
            else:
                self._active_voice_command_map = dict(_ACTIVE_COMMAND_TABLE)
            self._max_command_phrase_word_count = max(
                (len(k.split()) for k in self._active_voice_command_map), default=1)
            # User-editable punctuation map (phrase -> [char, sp_before, sp_after]).
            loaded_punctuation_map = config_file_data.get("punteggiatura_map")
            if isinstance(loaded_punctuation_map, dict) and loaded_punctuation_map:
                self._active_punctuation_map = {
                    str(k): (v[0], bool(v[1]), bool(v[2]))
                    for k, v in loaded_punctuation_map.items()
                    if isinstance(v, (list, tuple)) and len(v) == 3}
            else:
                self._active_punctuation_map = self._get_builtin_punctuation_table()
        except Exception:
            self._numbers_conversion_enabled = True
            self._punctuation_conversion_enabled = True
            self._voice_commands_enabled = True
            self._verbose_info_popups_enabled = False
            self._debug_error_popups_enabled = True
            self._verbose_command_logging_enabled = False
            self._active_voice_command_map = dict(_ACTIVE_COMMAND_TABLE)
            self._max_command_phrase_word_count = _MAX_COMMAND_PHRASE_WORD_COUNT
            self._active_punctuation_map = self._get_builtin_punctuation_table()

    def _save_config_to_file(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"numeri": self._numbers_conversion_enabled,
                           "punteggiatura": self._punctuation_conversion_enabled,
                           "comandi": self._voice_commands_enabled,
                           "verbose": self._verbose_info_popups_enabled,
                           "debug": self._debug_error_popups_enabled,
                           "verbose-logging": self._verbose_command_logging_enabled,
                           "comandi_map": self._active_voice_command_map,
                           "punteggiatura_map": {
                               k: [c, sb, sa]
                               for k, (c, sb, sa) in self._active_punctuation_map.items()},
                           }, f, indent=2, ensure_ascii=False)
        except Exception:
            log("salva config fallita:\n" + traceback.format_exc())

    def _on_engine_stopped(self):
        # Called by the worker thread when it ends: reset button to "not active".
        log("motore terminato -> aggiorno pulsante a OFF")
        _release_dictation_lock()
        self._update_microphone_button_icon(False)
        self._broadcast_all_listener_states()

    def _verbose_log(self, msg):
        """Diagnostic log for the voice command layer. No-op (single bool test)
        unless the 'verbose-logging' config flag is on, so it costs nothing in
        normal use."""
        if self._verbose_command_logging_enabled:
            log("[fn] " + msg)

    def _insert_dictated_text_at_cursor(self, raw_recognized_text):
        # When the command layer is off, the whole result is plain dictation.
        if not self._voice_commands_enabled:
            self._write_processed_text_to_document(raw_recognized_text)
            return
        # A single Vosk result can mix commands and dictation, e.g.
        # "attiva grassetto questo conta disattiva grassetto". Split it into
        # ordered segments and replay them in order: commands change state /
        # fire UNO actions, text runs get post-processed and inserted.
        for segment_kind, segment_payload in _split_text_into_command_segments(
                raw_recognized_text, self._active_voice_command_map,
                self._max_command_phrase_word_count):
            if segment_kind == "CMD":
                self._execute_voice_command_code(segment_payload)
            else:
                self._write_processed_text_to_document(segment_payload)

    def _write_processed_text_to_document(self, raw_text_from_vosk):
        """Post-process a raw text run (punctuation/numbers + case), then insert
        it at the cursor with the current character formatting applied."""
        processed_text = self._apply_capitalization_rules(self._apply_vosk_text_post_processing(raw_text_from_vosk))
        if not processed_text:
            return
        processed_text = processed_text + " "
        try:
            document = self.frame.getController().getModel()
            document_controller = document.getCurrentController()
            view_cursor = document_controller.getViewCursor()
            self._apply_character_formatting_to_cursor(view_cursor)
            document.getText().insertString(view_cursor, processed_text, False)
        except Exception:
            log("inserimento fallito:\n" + traceback.format_exc())

    # --- Voice commands ----------------------------------------------------
    def _execute_voice_command_code(self, code):
        """Execute one command action code (see the command tables on top).
        Font commands may carry an amount as "FONT_UP:5"."""
        self._verbose_log("comando: %s" % code)
        # Split an optional ":amount" argument (used by FONT_UP / FONT_DOWN).
        if ":" in code:
            code, argument_string = code.split(":", 1)
            command_argument_value = int(argument_string) if argument_string.lstrip("-").isdigit() else 0
        else:
            command_argument_value = 0
        if code == "BOLD_ON":
            self._bold_formatting_active = True
        elif code == "BOLD_OFF":
            self._bold_formatting_active = False
        elif code == "ITALIC_ON":
            self._italic_formatting_active = True
        elif code == "ITALIC_OFF":
            self._italic_formatting_active = False
        elif code == "UNDERLINE_ON":
            self._underline_formatting_active = True
        elif code == "UNDERLINE_OFF":
            self._underline_formatting_active = False
        elif code == "RESET_FORMAT":
            self._bold_formatting_active = self._italic_formatting_active = self._underline_formatting_active = False
            self._caps_lock_voice_active = self._capitalize_next_word_flag = False
            self._override_font_height_points = None
        elif code == "CAPSLOCK_ON":
            self._caps_lock_voice_active = True
        elif code == "CAPSLOCK_OFF":
            self._caps_lock_voice_active = False
        elif code == "NEXT_CAPITAL":
            self._capitalize_next_word_flag = True
        elif code == "TOGGLE_BULLET_LIST":
            self._fire_uno_dispatch_command(".uno:DefaultBullet")
        elif code == "TOGGLE_NUMBER_LIST":
            self._fire_uno_dispatch_command(".uno:DefaultNumbering")
        elif code == "TERMINATE_LIST":
            self._clear_list_formatting()
        elif code == "UNDO_LAST":
            self._fire_uno_dispatch_command(".uno:Undo")
        elif code == "REDO_LAST":
            self._fire_uno_dispatch_command(".uno:Redo")
        elif code == "PAGE_BREAK":
            self._fire_uno_dispatch_command(".uno:InsertPagebreak")
        elif code == "ALIGN_LEFT":
            self._fire_uno_dispatch_command(".uno:LeftPara")
        elif code == "ALIGN_CENTER":
            self._fire_uno_dispatch_command(".uno:CenterPara")
        elif code == "ALIGN_RIGHT":
            self._fire_uno_dispatch_command(".uno:RightPara")
        elif code == "ALIGN_JUSTIFY":
            self._fire_uno_dispatch_command(".uno:JustifyPara")
        elif code == "PRINT":
            self._fire_uno_dispatch_command(".uno:Print")
        elif code == "FONT_UP":
            self._change_font_height_by_delta(command_argument_value or FONT_STEP_DEFAULT)
        elif code == "FONT_DOWN":
            self._change_font_height_by_delta(-(command_argument_value or FONT_STEP_DEFAULT))
        elif code == "DATE_TODAY":
            self._insert_today_date_string()
        else:
            log("comando sconosciuto: %s" % code)

    def _insert_today_date_string(self):
        """Insert today's date at the cursor. Computed now via datetime, so it is
        always the current day (NOT a fixed/hardcoded date)."""
        date_format_string = "%m/%d/%Y" if LANG == "en" else "%d/%m/%Y"
        formatted_date_string = datetime.datetime.now().strftime(date_format_string)
        self._verbose_log("data inserita: %s" % formatted_date_string)
        self._insert_literal_string_at_cursor(formatted_date_string + " ")

    def _insert_literal_string_at_cursor(self, literal_text_to_insert):
        """Insert a literal string at the cursor with the current formatting,
        skipping the punctuation/number transform."""
        try:
            document = self.frame.getController().getModel()
            view_cursor = document.getCurrentController().getViewCursor()
            self._apply_character_formatting_to_cursor(view_cursor)
            document.getText().insertString(view_cursor, literal_text_to_insert, False)
        except Exception:
            log("inserimento letterale fallito:\n" + traceback.format_exc())

    def _change_font_height_by_delta(self, font_size_change_in_points):
        """Grow/shrink the size (points) used for the next dictated text. Starts
        from the current cursor height the first time, then accumulates. Never
        goes below 1pt."""
        starting_font_height_points = self._override_font_height_points
        if starting_font_height_points is None:
            try:
                view_cursor = self.frame.getController().getModel() \
                    .getCurrentController().getViewCursor()
                starting_font_height_points = float(view_cursor.CharHeight)
            except Exception:
                starting_font_height_points = 12.0
        self._override_font_height_points = max(1.0, starting_font_height_points + font_size_change_in_points)
        self._verbose_log("font height -> %s" % self._override_font_height_points)

    def _apply_capitalization_rules(self, input_text):
        """Apply the active case state to a text run: voice caps lock uppercases
        everything; NEXT_CAPITAL capitalizes only the first letter of the next
        word, then clears itself."""
        if self._caps_lock_voice_active:
            return input_text.upper()
        if self._capitalize_next_word_flag and input_text:
            for char_index, current_char in enumerate(input_text):
                if current_char.isalpha():
                    input_text = input_text[:char_index] + current_char.upper() + input_text[char_index + 1:]
                    break
            self._capitalize_next_word_flag = False
            self._verbose_log("maiuscolo iniziale applicato")
        return input_text

    def _apply_character_formatting_to_cursor(self, cursor):
        """Set bold/italic/underline character attributes on the (collapsed)
        view cursor so the text inserted right after inherits them."""
        try:
            from com.sun.star.awt.FontWeight import BOLD, NORMAL
            from com.sun.star.awt.FontSlant import ITALIC
            from com.sun.star.awt.FontSlant import NONE as SLANT_NONE
            from com.sun.star.awt.FontUnderline import SINGLE
            from com.sun.star.awt.FontUnderline import NONE as UL_NONE
            cursor.CharWeight = BOLD if self._bold_formatting_active else NORMAL
            cursor.CharPosture = ITALIC if self._italic_formatting_active else SLANT_NONE
            cursor.CharUnderline = SINGLE if self._underline_formatting_active else UL_NONE
            if self._override_font_height_points is not None:
                cursor.CharHeight = self._override_font_height_points
        except Exception:
            log("applica formato fallito:\n" + traceback.format_exc())

    def _fire_uno_dispatch_command(self, uno_command_string):
        """Fire a built-in UNO command (lists, undo) through the DispatchHelper
        on our frame."""
        try:
            service_manager = self.ctx.getServiceManager()
            dispatch_helper_service = service_manager.createInstanceWithContext(
                "com.sun.star.frame.DispatchHelper", self.ctx)
            dispatch_helper_service.executeDispatch(self.frame, uno_command_string, "", 0, ())
        except Exception:
            log("dispatch %s fallito:\n%s" % (uno_command_string, traceback.format_exc()))

    def _clear_list_formatting(self):
        """Drop list formatting from the current paragraph by clearing its
        numbering rules (works for both bullet and numbered lists)."""
        try:
            document = self.frame.getController().getModel()
            view_cursor = document.getCurrentController().getViewCursor()
            view_cursor.setPropertyValue("NumberingRules", None)
        except Exception:
            log("fine elenco fallito:\n" + traceback.format_exc())

    def _get_vosk_model_directory_path(self):
        package_info_provider = self.ctx.getByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        extension_package_url = package_info_provider.getPackageLocation(EXTENSION_ID)
        extension_package_local_path = unohelper.fileUrlToSystemPath(extension_package_url)
        return os.path.join(extension_package_local_path, "model")

    # --- Button state (toggles) -------------------------------------------
    def _get_command_button_state_for_url(self, full_toolbar_command_url):
        """Returns the 'pressed' state of the command associated with this URL."""
        if full_toolbar_command_url.endswith("togglenumbers"):
            return self._numbers_conversion_enabled
        if full_toolbar_command_url.endswith("togglepunct"):
            return self._punctuation_conversion_enabled
        if full_toolbar_command_url.endswith("togglecommands"):
            return self._voice_commands_enabled
        return self._check_if_listening()   # microphone toggle

    def _broadcast_all_listener_states(self):
        """Notifies every listener of the state of ITS own command (mic or toggle)."""
        for listener, url in list(self._toolbar_status_listeners):
            self._notify_single_listener_state(listener, url, self._get_command_button_state_for_url(url.Complete))

    def _notify_single_listener_state(self, listener, url, button_is_pressed):
        try:
            status_change_event = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
            status_change_event.FeatureURL = url
            status_change_event.IsEnabled = True
            status_change_event.Requery = False
            status_change_event.State = bool(button_is_pressed)   # True -> button shown as pressed
            listener.statusChanged(status_change_event)
        except Exception:
            log("notifica stato fallita:\n" + traceback.format_exc())

    # --- Runtime icons ----------------------------------------------------
    def _get_extension_package_url(self):
        """Returns the file:// URL of the installed extension folder."""
        package_info_provider = self.ctx.getByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        return package_info_provider.getPackageLocation(EXTENSION_ID)

    def _replace_toolbar_button_icon(self, toolbar_command_url, icon_filename_base):
        """Replaces at runtime the icon for `toolbar_command_url` with
        icons/<icon_filename_base>_16/_26.png via the Writer module's ImageManager."""
        try:
            from com.sun.star.beans import PropertyValue
            extension_package_base_url = self._get_extension_package_url()
            service_manager = self.ctx.getServiceManager()
            graphic_provider_service = service_manager.createInstanceWithContext(
                "com.sun.star.graphic.GraphicProvider", self.ctx)

            def _load_icon_graphic(icon_png_filename):
                url_property_value = PropertyValue()
                url_property_value.Name = "URL"
                url_property_value.Value = extension_package_base_url + "/icons/" + icon_png_filename
                return graphic_provider_service.queryGraphic((url_property_value,))

            ui_config_supplier_service = service_manager.createInstanceWithContext(
                "com.sun.star.ui.ModuleUIConfigurationManagerSupplier", self.ctx)
            ui_config_manager = ui_config_supplier_service.getUIConfigurationManager(
                "com.sun.star.text.TextDocument")
            image_manager = ui_config_manager.getImageManager()
            # ImageType 0 = small (default), 1 = large (SIZE_LARGE).
            image_manager.replaceImages(0, (toolbar_command_url,), (_load_icon_graphic(icon_filename_base + "_16.png"),))
            try:
                image_manager.replaceImages(1, (toolbar_command_url,), (_load_icon_graphic(icon_filename_base + "_26.png"),))
            except Exception:
                pass
            try:
                if image_manager.isModified():
                    image_manager.store()
            except Exception:
                pass
            log("icona %s -> %s" % (toolbar_command_url, icon_filename_base))
        except Exception:
            log("set icona fallita:\n" + traceback.format_exc())

    def _update_microphone_button_icon(self, currently_listening):
        """Microphone icon: red when listening, green when ready."""
        self._replace_toolbar_button_icon(PROTOCOL + "toggle",
                                "mic_stop" if currently_listening else "mic_start")

    # --- Feedback ----------------------------------------------------------
    def _show_error_message_popup(self, msg):
        """ERROR popup. Shown only if the 'debug' flag is active (default ON).
        The message is always written to the log file regardless."""
        log("errore: " + msg)
        if not self._debug_error_popups_enabled:
            return
        try:
            from com.sun.star.awt.MessageBoxType import ERRORBOX
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx)
            parent = self.frame.getContainerWindow() if self.frame else None
            box = toolkit.createMessageBox(parent, ERRORBOX, 1, "Dettatura Vocale", msg)
            box.execute()
        except Exception:
            log("messagebox fallita: " + msg)

    def _show_info_message_popup(self, msg):
        """INFORMATIONAL popup (toggle confirmation). Shown only if the 'verbose'
        flag is active (default OFF)."""
        if not self._verbose_info_popups_enabled:
            return
        try:
            from com.sun.star.awt.MessageBoxType import INFOBOX
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx)
            parent = self.frame.getContainerWindow() if self.frame else None
            box = toolkit.createMessageBox(parent, INFOBOX, 1, "Voice Dictation", msg)
            box.execute()
        except Exception:
            log("infobox fallita: " + msg)


# ===========================================================================
# Component registration (required by pyuno).
# ===========================================================================
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    DictationHandler,
    IMPL_NAME,
    SERVICE_NAMES,
)
log("componente registrato: %s" % IMPL_NAME)
