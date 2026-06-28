#!/usr/bin/env python3
"""_pack.py - applies substitutions to the staging folder and creates the .oxt.

Two tasks:

1) Substitutions for it/en COEXISTENCE. Sources use consistent prefixes;
   by injecting the language code into the prefix, identifier/ImplementationName/
   protocol/registry node names become distinct between the two extensions,
   so LibreOffice keeps them separate:
     org.libreitalia.dettaturavocale  ->  org.libreitalia.dettaturavocale.<lang>
     vnd.libreitalia.dettatura:       ->  vnd.libreitalia.dettatura.<lang>:
   Plus the explicit tokens in description.xml:
     @PLATFORM@  @MODEL_LANG_IT@  @MODEL_LANG_EN@

2) Zip the staging folder into a .oxt (ZIP with description.xml and META-INF/
   at the root), excluding cache/build artifacts.

Usage:
  _pack.py --stage DIR --out FILE.oxt --lang it --lo-platform linux_x86_64 \
           --model-lang-it Italiano --model-lang-en Italian
"""
import argparse
import os
import zipfile

# Text file extensions on which to apply substitutions.
TEXT_EXT = (".xml", ".xcu", ".py")
# Patterns to exclude from the final zip.
SKIP = ("__pycache__", ".DS_Store", "Thumbs.db")


def substitute(stage, lang, lo_platform, model_display_name_italian, model_display_name_english, version):
    text_substitution_map = {
        "org.libreitalia.dettaturavocale": f"org.libreitalia.dettaturavocale.{lang}",
        "vnd.libreitalia.dettatura:": f"vnd.libreitalia.dettatura.{lang}:",
        "@PLATFORM@": lo_platform,
        "@MODEL_LANG_IT@": model_display_name_italian,
        "@MODEL_LANG_EN@": model_display_name_english,
        "@LANG@": lang,        # text_processing.py: selects it/en punctuation+number tables
        "@VERSION@": version,  # description.xml: extension version (from git tag)
    }
    for root, _dirs, files in os.walk(stage):
        for name in files:
            if not name.endswith(TEXT_EXT):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as f:
                file_text_content = f.read()
            for old, new in text_substitution_map.items():
                file_text_content = file_text_content.replace(old, new)
            with open(path, "w", encoding="utf-8") as f:
                f.write(file_text_content)


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
                full_file_system_path = os.path.join(root, name)
                archive_zip_relative_path = os.path.relpath(full_file_system_path, stage)  # ZIP root = contents of stage/
                z.write(full_file_system_path, archive_zip_relative_path)


def main():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--stage", required=True)
    argument_parser.add_argument("--out", required=True)
    argument_parser.add_argument("--lang", required=True)
    argument_parser.add_argument("--lo-platform", required=True)
    argument_parser.add_argument("--model-lang-it", required=True)
    argument_parser.add_argument("--model-lang-en", required=True)
    argument_parser.add_argument("--version", default="0.0.0-dev")
    parsed_arguments = argument_parser.parse_args()
    substitute(parsed_arguments.stage, parsed_arguments.lang, parsed_arguments.lo_platform, parsed_arguments.model_lang_it, parsed_arguments.model_lang_en, parsed_arguments.version)
    make_oxt(parsed_arguments.stage, parsed_arguments.out)
    print(f">> Pacchetto pronto: {parsed_arguments.out}")


if __name__ == "__main__":
    main()
