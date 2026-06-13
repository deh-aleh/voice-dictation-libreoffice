#!/usr/bin/env python3
"""_pack.py - applica le sostituzioni alla cartella di staging e crea l'.oxt.

Due compiti:

1) Sostituzioni per la COESISTENZA it/en. I sorgenti usano prefissi coerenti;
   iniettando il codice lingua nel prefisso, identifier/ImplementationName/
   protocollo/nomi-nodo del registro diventano distinti tra le due estensioni,
   cosi' LibreOffice le tiene separate:
     org.libreitalia.dettaturavocale  ->  org.libreitalia.dettaturavocale.<lang>
     vnd.libreitalia.dettatura:       ->  vnd.libreitalia.dettatura.<lang>:
   Piu' i token espliciti in description.xml:
     @PLATFORM@  @MODEL_LANG_IT@  @MODEL_LANG_EN@

2) Zip della cartella di staging in un .oxt (ZIP con description.xml e META-INF/
   alla radice), escludendo cache/artefatti.

Uso:
  _pack.py --stage DIR --out FILE.oxt --lang it --lo-platform linux_x86_64 \
           --model-lang-it Italiano --model-lang-en Italian
"""
import argparse
import os
import zipfile

# File testuali su cui applicare le sostituzioni.
TEXT_EXT = (".xml", ".xcu", ".py")
# Pattern da escludere dallo zip finale.
SKIP = ("__pycache__", ".DS_Store", "Thumbs.db")


def substitute(stage, lang, lo_platform, ml_it, ml_en, version):
    repl = {
        "org.libreitalia.dettaturavocale": f"org.libreitalia.dettaturavocale.{lang}",
        "vnd.libreitalia.dettatura:": f"vnd.libreitalia.dettatura.{lang}:",
        "@PLATFORM@": lo_platform,
        "@MODEL_LANG_IT@": ml_it,
        "@MODEL_LANG_EN@": ml_en,
        "@LANG@": lang,        # trasformazione.py: selects it/en punctuation+number tables
        "@VERSION@": version,  # description.xml: extension version (from git tag)
    }
    for root, _dirs, files in os.walk(stage):
        for name in files:
            if not name.endswith(TEXT_EXT):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            for old, new in repl.items():
                text = text.replace(old, new)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)


def make_oxt(stage, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(stage):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for name in files:
                if name.endswith((".pyc", ".pyo")) or name in SKIP:
                    continue
                full = os.path.join(root, name)
                arc = os.path.relpath(full, stage)  # radice ZIP = contenuto di stage/
                z.write(full, arc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", required=True)
    ap.add_argument("--lo-platform", required=True)
    ap.add_argument("--model-lang-it", required=True)
    ap.add_argument("--model-lang-en", required=True)
    ap.add_argument("--version", default="0.0.0-dev")
    a = ap.parse_args()
    substitute(a.stage, a.lang, a.lo_platform, a.model_lang_it, a.model_lang_en, a.version)
    make_oxt(a.stage, a.out)
    print(f">> Pacchetto pronto: {a.out}")


if __name__ == "__main__":
    main()
