# -*- coding: utf-8 -*-
"""
dettatura.py - Componente UNO (ProtocolHandler) per la dettatura vocale offline
               in LibreOffice Writer tramite Vosk.

Flusso:
    1. Click sul pulsante (Addons.xcu) -> URL "vnd.libreitalia.dettatura:toggle".
    2. ProtocolHandler.xcu instrada l'URL a questo componente.
    3. dispatch() avvia/ferma un thread di ascolto audio.
    4. Il thread riconosce il parlato con Vosk e inserisce il testo al cursore.

Feedback visivo:
    Il pulsante e' un "toggle": quando la dettatura e' attiva LibreOffice lo
    mostra PREMUTO/evidenziato. Lo stato e' notificato agli XStatusListener della
    toolbar tramite FeatureStateEvent.State (True = in ascolto).

Diagnostica:
    Tutto viene loggato in <tmp>/dettatura_libreoffice.log, cosi' e' possibile
    capire se il componente viene caricato e se il click arriva, anche quando la
    UI non mostra nulla. Percorso tipico: /tmp/dettatura_libreoffice.log
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
# Priorita' alle dipendenze bundlate nell'estensione.
# LibreOffice aggiunge <oxt>/pythonpath in CODA a sys.path: cosi' eventuali
# pacchetti di sistema (es. un tqdm rotto in /usr/lib/.../site-packages)
# verrebbero caricati al posto dei nostri. Inserendolo in TESTA, il nostro
# bundle self-consistent vince sempre.
_PYTHONPATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pythonpath")
if os.path.isdir(_PYTHONPATH) and sys.path[0:1] != [_PYTHONPATH]:
    sys.path.insert(0, _PYTHONPATH)

from com.sun.star.frame import XDispatchProvider, XDispatch
from com.sun.star.lang import XServiceInfo, XInitialization

# ---------------------------------------------------------------------------
# Costanti di registrazione. Devono combaciare con ProtocolHandler.xcu.
# ---------------------------------------------------------------------------
IMPL_NAME = "org.libreitalia.dettaturavocale.ProtocolHandler"
SERVICE_NAMES = ("com.sun.star.frame.ProtocolHandler",)
PROTOCOL = "vnd.libreitalia.dettatura:"
EXTENSION_ID = "org.libreitalia.dettaturavocale"

# Parametri audio richiesti dai modelli Vosk (mono, 16 kHz, PCM 16-bit).
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

# File di log per la diagnostica.
LOG_PATH = os.path.join(tempfile.gettempdir(), "dettatura_libreoffice.log")


def log(msg):
    """Scrive una riga timestampata nel file di log (best-effort)."""
    try:
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (ts, msg))
    except Exception:
        pass


# Traccia gia' il semplice caricamento del modulo: se questa riga non compare
# nel log, il componente Python non viene proprio caricato da LibreOffice.
log("=== modulo dettatura.py caricato (pid %s) ===" % os.getpid())


# ---------------------------------------------------------------------------
# Mutua esclusione tra le estensioni di lingua diversa (it, en, ...).
# Possono coesistere INSTALLATE, ma NON devono ascoltare il microfono insieme.
# Usiamo un lockfile dal nome FISSO (non per-lingua): cosi' l'estensione IT
# "vede" il lock di quella EN e viceversa. Contiene PID e identifier del titolare.
# ---------------------------------------------------------------------------
LOCK_PATH = os.path.join(tempfile.gettempdir(), "voice-dictation.lock")


def _pid_vivo(pid):
    """True se il processo con questo PID e' ancora in esecuzione."""
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        # Su Windows os.kill(pid, 0) puo' TERMINARE il processo: evitarlo.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return True  # in dubbio, considero vivo (non rubo il lock)
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        import errno
        return e.errno == errno.EPERM  # esiste ma non ho i permessi


def _leggi_lock():
    """Ritorna (pid, identifier) del lock, o (None, None) se assente/illeggibile."""
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            pid = int(f.readline().strip())
            ident = f.readline().strip()
        return pid, ident
    except Exception:
        return None, None


def _acquisisci_lock():
    """Prova a prendere il lock. False se un'altra istanza VIVA lo detiene."""
    try:
        if os.path.exists(LOCK_PATH):
            pid, ident = _leggi_lock()
            if pid and _pid_vivo(pid):
                # Occupato, a meno che non siamo noi stessi (stesso pid+identifier).
                if not (pid == os.getpid() and ident == EXTENSION_ID):
                    log("lock occupato da pid=%s ident=%s" % (pid, ident))
                    return False
            # altrimenti lock stantio (processo morto): lo sovrascrivo
        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            f.write("%d\n%s\n" % (os.getpid(), EXTENSION_ID))
        return True
    except Exception:
        log("lock: errore acquisizione:\n" + traceback.format_exc())
        return True  # non bloccare l'uso per un errore di I/O


def _rilascia_lock():
    """Rimuove il lock solo se e' nostro (stesso pid+identifier). Idempotente."""
    try:
        if not os.path.exists(LOCK_PATH):
            return
        pid, ident = _leggi_lock()
        if pid == os.getpid() and ident == EXTENSION_ID:
            os.remove(LOCK_PATH)
    except Exception:
        log("lock: errore rilascio:\n" + traceback.format_exc())


def _stub_dipendenze_opzionali():
    """Neutralizza dipendenze opzionali che si rompono sotto il loader UNO.

    vosk importa tqdm, che fa:
        try: from envwrap import envwrap
        except ModuleNotFoundError: pass
    L'import hook di LibreOffice (uno.py) pero' rilancia ImportError (classe
    base) invece di ModuleNotFoundError, quindi il guard di tqdm non scatta e
    l'import esplode. Registriamo uno stub 'envwrap' in sys.modules cosi'
    l'import riesce sempre. tqdm non ci serve: vosk lo usa solo per la barra di
    avanzamento del download del modello (che noi bundliamo gia')."""
    import types as _types
    if "envwrap" not in sys.modules:
        m = _types.ModuleType("envwrap")

        def envwrap(prefix, types=None, is_method=False, **_kw):
            # Decoratore identita': lascia la funzione invariata.
            def deco(fn):
                return fn
            return deco

        m.envwrap = envwrap
        sys.modules["envwrap"] = m
        log("stub envwrap registrato")


def _diagnostica_ambiente():
    """Logga info utili a capire i problemi di caricamento native (Windows in primis)."""
    try:
        log("--- DIAGNOSTICA ---")
        log("platform=%s machine=%s" % (sys.platform, getattr(os, "uname", lambda: "?")() if hasattr(os, "uname") else "?"))
        log("python=%s" % sys.version.replace("\n", " "))
        log("pythonpath bundle=%s" % _PYTHONPATH)
        if os.path.isdir(_PYTHONPATH):
            voci = sorted(os.listdir(_PYTHONPATH))
            backend = [v for v in voci if v.startswith("_cffi_backend")]
            log("_cffi_backend presenti: %s" % backend)
            log("_sounddevice_data presente: %s" % os.path.isdir(os.path.join(_PYTHONPATH, "_sounddevice_data")))
            voskdir = os.path.join(_PYTHONPATH, "vosk")
            if os.path.isdir(voskdir):
                native = [v for v in os.listdir(voskdir) if v.lower().endswith((".dll", ".so", ".dylib"))]
                log("native in vosk/: %s" % native)
        # Su Windows le DLL dipendenti (libvosk -> libstdc++/libgcc/winpthread)
        # vanno rese trovabili: aggiungo le cartelle al search path delle DLL.
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
# Motore di riconoscimento: Vosk + acquisizione audio nel suo thread.
# ===========================================================================
class MotoreDettatura:
    """Gestisce ascolto audio e riconoscimento in un thread separato.

    Disaccoppiato da UNO: il testo riconosciuto viene passato alla callback
    `inserisci_testo`. Quando il thread termina (stop o errore) invoca
    `on_stop` cosi' il chiamante puo' aggiornare lo stato del pulsante.
    """

    def __init__(self, model_path, inserisci_testo, on_stop=None):
        self._model_path = model_path
        self._inserisci_testo = inserisci_testo
        self._on_stop = on_stop

        self._thread = None
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()

    @property
    def in_ascolto(self):
        return self._thread is not None and self._thread.is_alive()

    def avvia(self):
        if self.in_ascolto:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._ciclo, name="DettaturaVosk", daemon=True)
        self._thread.start()

    def ferma(self):
        # Non si fa join(): siamo nel thread della UI e non vogliamo bloccarla.
        self._stop_event.set()
        self._thread = None

    # --- Esecuzione nel thread worker -------------------------------------
    def _callback_audio(self, indata, frames, time_info, status):
        if status:
            log("audio status: %s" % status)
        self._audio_queue.put(bytes(indata))

    def _ciclo(self):
        try:
            log("thread dettatura: avvio")
            _diagnostica_ambiente()
            _stub_dipendenze_opzionali()

            # Import separati: se fallisce, il log dice ESATTAMENTE quale.
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

            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                   dtype="int16", channels=1,
                                   callback=self._callback_audio):
                log("ascolto avviato")
                while not self._stop_event.is_set():
                    try:
                        data = self._audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        testo = json.loads(recognizer.Result()).get("text", "")
                        if testo:
                            log("riconosciuto: %r" % testo)
                            self._inserisci_testo(testo + " ")

                finale = json.loads(recognizer.FinalResult()).get("text", "")
                if finale:
                    self._inserisci_testo(finale + " ")
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
# Componente UNO: riceve il click, pilota il motore, aggiorna lo stato pulsante.
# ===========================================================================
class DettaturaHandler(unohelper.Base, XServiceInfo, XDispatchProvider,
                       XDispatch, XInitialization):

    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None
        self.motore = None
        # Listener della toolbar (per evidenziare il pulsante quando attivo).
        self._listeners = []   # lista di (XStatusListener, URL)
        log("DettaturaHandler creato")

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
        if not url.Complete.startswith(PROTOCOL):
            return
        # L'azione e' la parte dopo il protocollo: "toggle" oppure "openlog".
        azione = url.Complete[len(PROTOCOL):]
        try:
            if azione == "openlog":
                self._apri_cartella_log()
            else:
                self._toggle()
        except Exception:
            tb = traceback.format_exc()
            log("ECCEZIONE in dispatch:\n" + tb)
            self._messaggio("Errore:\n" + tb)

    def _apri_cartella_log(self):
        """Apre la cartella che contiene il file di log nel file manager di sistema."""
        cartella = os.path.dirname(LOG_PATH)
        log("apro cartella log: %s" % cartella)
        try:
            if sys.platform.startswith("win"):
                os.startfile(cartella)  # noqa: stesso effetto di doppio click
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", cartella])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", cartella])
        except Exception:
            log("apertura cartella fallita:\n" + traceback.format_exc())
        # In ogni caso mostro all'utente il percorso esatto del log.
        self._messaggio("Cartella dei log:\n%s\n\nFile di log:\n%s" % (cartella, LOG_PATH))

    def addStatusListener(self, listener, url):
        # La toolbar registra qui un listener per conoscere lo stato del comando.
        self._listeners.append((listener, url))
        # Invia subito lo stato corrente (abilitato, non in ascolto).
        self._notifica_stato(listener, url, self._in_ascolto())

    def removeStatusListener(self, listener, url):
        self._listeners = [(l, u) for (l, u) in self._listeners if l != listener]

    # --- Logica applicativa ------------------------------------------------
    def _in_ascolto(self):
        return self.motore is not None and self.motore.in_ascolto

    def _toggle(self):
        if self.motore is None:
            self.motore = MotoreDettatura(
                model_path=self._percorso_modello(),
                inserisci_testo=self._inserisci_al_cursore,
                on_stop=self._on_motore_stop,
            )

        if self.motore.in_ascolto:
            log("toggle -> STOP")
            self.motore.ferma()
            _rilascia_lock()
        else:
            # Mutua esclusione: non partire se un'altra lingua/finestra ascolta gia'.
            if not _acquisisci_lock():
                self._messaggio(
                    "Dettatura gia' attiva (un'altra lingua o finestra).\n"
                    "Fermala prima di iniziare qui.")
                log("toggle START rifiutato: lock occupato")
                return
            log("toggle -> START (modello: %s)" % self._percorso_modello())
            self.motore.avvia()

        self._broadcast_stato(self._in_ascolto())

    def _on_motore_stop(self):
        # Chiamato dal thread quando termina: riporta il pulsante a "non attivo".
        log("motore terminato -> aggiorno pulsante a OFF")
        _rilascia_lock()
        self._broadcast_stato(False)

    def _inserisci_al_cursore(self, testo):
        try:
            doc = self.frame.getController().getModel()
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            doc.getText().insertString(view_cursor, testo, False)
        except Exception:
            log("inserimento fallito:\n" + traceback.format_exc())

    def _percorso_modello(self):
        pip = self.ctx.getByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation(EXTENSION_ID)
        base_path = unohelper.fileUrlToSystemPath(base_url)
        return os.path.join(base_path, "model")

    # --- Stato pulsante (toggle) ------------------------------------------
    def _broadcast_stato(self, in_ascolto):
        """Notifica a tutti i listener della toolbar il nuovo stato premuto."""
        for listener, url in list(self._listeners):
            self._notifica_stato(listener, url, in_ascolto)

    def _notifica_stato(self, listener, url, in_ascolto):
        try:
            ev = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
            ev.FeatureURL = url
            ev.IsEnabled = True
            ev.Requery = False
            ev.State = bool(in_ascolto)   # True -> pulsante mostrato premuto
            listener.statusChanged(ev)
        except Exception:
            log("notifica stato fallita:\n" + traceback.format_exc())

    # --- Feedback errori ---------------------------------------------------
    def _messaggio(self, msg):
        try:
            from com.sun.star.awt.MessageBoxType import ERRORBOX
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx)
            parent = self.frame.getContainerWindow() if self.frame else None
            box = toolkit.createMessageBox(parent, ERRORBOX, 1, "Dettatura Vocale", msg)
            box.execute()
        except Exception:
            log("messagebox fallita: " + msg)


# ===========================================================================
# Registrazione del componente (richiesta da pyuno).
# ===========================================================================
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    DettaturaHandler,
    IMPL_NAME,
    SERVICE_NAMES,
)
log("componente registrato: %s" % IMPL_NAME)
