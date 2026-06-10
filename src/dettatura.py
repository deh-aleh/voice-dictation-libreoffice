# -*- coding: utf-8 -*-
"""
dettatura.py - Componente UNO (ProtocolHandler) per la dettatura vocale offline
               in LibreOffice Writer tramite Vosk.

Flusso generale:
    1. L'utente clicca il pulsante in toolbar (Addons.xcu).
    2. LibreOffice traduce il click in un dispatch verso l'URL
       "vnd.libreitalia.dettatura:toggle".
    3. ProtocolHandler.xcu instrada quell'URL a questo componente.
    4. dispatch() avvia/ferma un thread di ascolto audio.
    5. Il thread riconosce il parlato con Vosk e inserisce il testo
       al cursore di Writer tramite l'API UNO.

Best practice adottate:
    - Componente UNO registrato via unohelper.ImplementationHelper.
    - L'audio gira in un thread separato: la UI di LO NON si blocca mai.
    - Le dipendenze native (vosk, sounddevice) sono caricate da <oxt>/pythonpath,
      che LibreOffice aggiunge automaticamente a sys.path per i componenti Python
      di un'estensione.
    - Il modello Vosk viene localizzato a runtime via PackageInformationProvider,
      cosi' funziona indipendentemente da dove l'utente ha installato l'estensione.
"""

import os
import sys
import json
import queue
import threading
import traceback

import uno
import unohelper

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


# ===========================================================================
# Motore di riconoscimento: incapsula Vosk + acquisizione audio nel suo thread.
# ===========================================================================
class MotoreDettatura:
    """Gestisce il ciclo di vita dell'ascolto audio e del riconoscimento.

    L'inserimento del testo nel documento avviene tramite la callback
    `inserisci_testo`, fornita dal chiamante, cosi' il motore resta
    disaccoppiato dall'API UNO.
    """

    def __init__(self, model_path, inserisci_testo, logga=print):
        self._model_path = model_path
        self._inserisci_testo = inserisci_testo
        self._logga = logga

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
        self._stop_event.set()
        # Non si fa join() qui: siamo nel thread della UI e non vogliamo bloccarla.
        self._thread = None

    # --- Esecuzione nel thread worker -------------------------------------
    def _callback_audio(self, indata, frames, time_info, status):
        """Chiamata da sounddevice per ogni blocco audio acquisito."""
        if status:
            self._logga("Audio status: %s" % status)
        self._audio_queue.put(bytes(indata))

    def _ciclo(self):
        """Loop principale di riconoscimento (gira nel thread separato)."""
        try:
            # Import ritardato: avviene nel thread, dopo che pythonpath e' su sys.path.
            from vosk import Model, KaldiRecognizer
            import sounddevice as sd

            if not os.path.isdir(self._model_path):
                self._logga("Modello Vosk non trovato in: %s" % self._model_path)
                return

            model = Model(self._model_path)
            recognizer = KaldiRecognizer(model, SAMPLE_RATE)
            recognizer.SetWords(False)

            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                   dtype="int16", channels=1,
                                   callback=self._callback_audio):
                self._logga("Dettatura avviata.")
                while not self._stop_event.is_set():
                    try:
                        data = self._audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if recognizer.AcceptWaveform(data):
                        # Frase completa riconosciuta.
                        testo = json.loads(recognizer.Result()).get("text", "")
                        if testo:
                            self._inserisci_testo(testo + " ")

                # Svuota l'ultimo parziale rimasto nel recognizer.
                finale = json.loads(recognizer.FinalResult()).get("text", "")
                if finale:
                    self._inserisci_testo(finale + " ")

            self._logga("Dettatura fermata.")

        except Exception:
            self._logga("Errore nel thread di dettatura:\n" + traceback.format_exc())


# ===========================================================================
# Componente UNO: riceve il click e pilota il MotoreDettatura.
# ===========================================================================
class DettaturaHandler(unohelper.Base, XServiceInfo, XDispatchProvider,
                       XDispatch, XInitialization):

    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None          # impostato in initialize()
        self.motore = None

    # --- XInitialization ---------------------------------------------------
    def initialize(self, args):
        # LibreOffice passa il frame corrente come primo argomento.
        if args:
            self.frame = args[0]

    # --- XServiceInfo ------------------------------------------------------
    def getImplementationName(self):
        return IMPL_NAME

    def supportsService(self, name):
        return name in SERVICE_NAMES

    def getSupportedServiceNames(self):
        return SERVICE_NAMES

    # --- XDispatchProvider -------------------------------------------------
    def queryDispatch(self, url, target_frame_name, search_flags):
        # Accettiamo solo gli URL del nostro protocollo.
        if url.Complete.startswith(PROTOCOL):
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags)
                     for r in requests)

    # --- XDispatch ---------------------------------------------------------
    def dispatch(self, url, args):
        if not url.Complete.startswith(PROTOCOL):
            return
        try:
            self._toggle()
        except Exception:
            self._messaggio("Errore: " + traceback.format_exc())

    def addStatusListener(self, listener, url):
        pass

    def removeStatusListener(self, listener, url):
        pass

    # --- Logica applicativa ------------------------------------------------
    def _toggle(self):
        """Avvia se fermo, ferma se in ascolto."""
        if self.motore is None:
            self.motore = MotoreDettatura(
                model_path=self._percorso_modello(),
                inserisci_testo=self._inserisci_al_cursore,
                logga=self._log,
            )

        if self.motore.in_ascolto:
            self.motore.ferma()
        else:
            self.motore.avvia()

    def _inserisci_al_cursore(self, testo):
        """Inserisce `testo` esattamente dove si trova il cursore in Writer.

        Usa il view-cursor del controller corrente: e' la posizione visibile
        del cursore dell'utente. insertString lo fa avanzare automaticamente.
        """
        try:
            doc = self.frame.getController().getModel()
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            doc.getText().insertString(view_cursor, testo, False)
        except Exception:
            self._log("Inserimento fallito:\n" + traceback.format_exc())

    def _percorso_modello(self):
        """Restituisce il path su filesystem della cartella `model/` dentro l'oxt."""
        pip = self.ctx.getByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation(EXTENSION_ID)        # es. file:///.../oxt
        base_path = unohelper.fileUrlToSystemPath(base_url)
        return os.path.join(base_path, "model")

    # --- Utilita' di feedback ---------------------------------------------
    def _log(self, msg):
        # In assenza di un logger UNO, stdout va nel log di LibreOffice/console.
        sys.stdout.write("[Dettatura] %s\n" % msg)
        sys.stdout.flush()

    def _messaggio(self, msg):
        """Mostra un messaggio modale all'utente (per gli errori bloccanti)."""
        try:
            from com.sun.star.awt.MessageBoxType import ERRORBOX
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx)
            parent = self.frame.getContainerWindow() if self.frame else None
            box = toolkit.createMessageBox(parent, ERRORBOX, 1, "Dettatura Vocale", msg)
            box.execute()
        except Exception:
            self._log(msg)


# ===========================================================================
# Registrazione del componente (richiesta da pyuno).
# ===========================================================================
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    DettaturaHandler,
    IMPL_NAME,
    SERVICE_NAMES,
)
