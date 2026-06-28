# Voice Dictation for LibreOffice Writer

🇮🇹 [Leggi in italiano](README.md)

---

## Why I made this

There are many people who can't use a keyboard the way most of us do: maybe they have a disability, maybe their hands hurt, maybe they grew up before computers existed and a keyboard still feels like something foreign, or maybe they are just always in a hurry.

There are also people who had an accident, or a medical condition, and typing has become painful or impossible.

I wanted to give these people a way to just **talk** and have their words appear on screen. No complicated setup, no subscription, no sending your voice to some company's server in another country.

This extension lets you speak directly into LibreOffice Writer. You press a button, you talk, the text appears. That's it.

And the best part? **Everything stays on your computer.** Your voice never leaves your machine. No internet required. No account. No cloud. Just you and your microphone.

---

## Features

- 🔒 **100% offline** — your voice data never leaves your computer, ever
- 🌍 **Italian and English** — separate `.oxt` file for each language
- 🧩 **Self-contained** — Python dependencies and the speech model are bundled inside the `.oxt`, no extra installation needed
- 🖱️ **One button** — click to start, click to stop; the microphone icon turns red when listening
- ✍️ **Punctuation by voice** — say *"period"* → `.`, *"comma"* → `,`, *"new paragraph"* → double line break, and more
- 🔢 **Numbers by voice** — say *"twenty three"* → `23`, *"two thousand five hundred"* → `2500`
- 🎛️ **Formatting commands** — bold, italic, underline, lists, alignment, font size, print, undo/redo — all by voice, no mouse needed
- 🔘 **Toggles** — you can turn numbers, punctuation, and formatting commands on or off independently
- 🛠️ **Editable dictionaries** — you can rename any voice command or punctuation phrase from the config file
- 🔁 **Italian + English can coexist** — install both, but only one listens at a time
- ⚡ **Non-blocking** — audio runs in a background thread, LibreOffice stays responsive

---

## Installation (end user)

1. Go to the [Releases page](../../releases) and download the `.oxt` for your language and platform, for example `voice-dictation-[LANGUAGE]-[PLATFORM].oxt`.
2. Open LibreOffice → **Tools → Extension Manager → Add…** → select the `.oxt` file.
3. Restart LibreOffice.
4. Open Writer: you will see the **Start/Stop Dictation** button in the toolbar.

You can install the Italian and English versions at the same time. You will have two buttons, but only one can listen at a time.

---

## How to use it

1. Click inside the document where you want to write.
2. Click **Start Dictation** and start talking.
3. The text appears in real time as you speak.
4. Click again to stop.

---

## Punctuation by voice

Say these words and they will be converted to the corresponding symbol, with correct spacing (no space before `.` or `)`, etc.).

You can edit the full list in the config file (`punteggiatura_map`).

| Output | English phrase |
|---|---|
| `.` | period · full stop |
| `,` | comma |
| `;` | semicolon |
| `:` | colon |
| `?` | question mark |
| `!` | exclamation mark · exclamation point |
| new line | new line |
| double line break | new paragraph |
| `(` | open parenthesis · open paren |
| `)` | close parenthesis · close paren |
| `"` | open/close quote(s) |
| `-` | hyphen |
| `—` | dash · em dash |
| `*` | asterisk |
| `/` | slash |
| `@` | at sign |
| `$` | dollar sign · dollars |
| `€` | euro |
| `£` | pound sign · pounds |
| `%` | percent · percentage sign |
| `#` | hashtag · number sign |
| `...` | ellipsis |
| `etc. etc.` | etcetera |

---

## Numbers by voice

Spoken numbers become digits: *"twenty three"* → `23`, *"two thousand five hundred"* → `2500`. Works with both separated tokens and concatenated forms.

Two independent numbers stay separate: *"twenty three fifty four"* → `23 54` (not `77`).

---

## Formatting commands by voice

Say these phrases while dictating — they trigger an action instead of being typed. Commands and normal text can be mixed in the same sentence, like *"bold on this is important bold off"*.

You can turn all commands on or off with the **Formatting commands** toggle in the Dictation menu. When off, these phrases are typed as normal text.

The full list is editable in the config file (`comandi_map`).

| Action | English phrase |
|---|---|
| Bullet list on/off | bullet list · bulleted list |
| Numbered list on/off | numbered list |
| End list | end list |
| Bold on | bold on · start bold |
| Bold off | bold off · end bold |
| Italic on | italic on · start italic |
| Italic off | italic off · end italic |
| Underline on | underline on |
| Underline off | underline off |
| Capitalize next word | capitalize · capital |
| ALL CAPS on | all caps · caps on |
| ALL CAPS off | caps off · end caps |
| Undo last block | delete last · scratch that |
| Redo | redo |
| Clear formatting | normal text |
| Page break | page break · insert page break |
| Align left | align left |
| Align center | align center |
| Align right | align right |
| Justify | justify · justified |
| Print (opens dialog) | print |
| Increase font size (by N, default 4) | increase font · bigger font |
| Decrease font size (by N, default 4) | decrease font · smaller font |
| Insert today's date | return date · insert date · current date |

For font size you can say the amount: *"increase font five"* → +5pt. Without a number it uses the default step (4pt).

---

## How it works (short version)

```
[Button click] --Addons.xcu--> URL "vnd.libreitalia.dettatura.<lang>:toggle"
       --ProtocolHandler.xcu--> DettaturaHandler.dispatch() (dettatura.py)
       --> lockfile: only one language/window listens at a time
       --> audio thread: sounddevice -> Vosk -> raw text
       --> trasformazione.py: punctuation + numbers -> final text
       --> UNO: insertString(view_cursor, text)
```

Full technical detail: [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

---

## Project structure

```
dettatura-vocale-libreoffice/
├── README.md                       # in Italian
├── README_EN.md                    # in English (this file)
├── LICENSE                         # MIT
├── Makefile                        # local build: make all LANG=en PLATFORM=linux_x86_64
├── .github/workflows/
│   └── release.yml                 # CI: 3 OS × 2 languages → 6 oxt on tag v*
├── docs/
│   ├── ARCHITETTURA.md             # how LibreOffice loads native libs from the oxt
│   ├── STATO_PROGETTO.md           # current status / roadmap
│   └── FUNZIONAMENTO.md             # step-by-step flow from build to text
├── scripts/
│   ├── fetch_deps.sh <plat>        # native deps + _cffi_backend 3.9-3.14 -> build/deps/
│   ├── fetch_model.sh <lang>       # downloads Vosk model -> build/models/<lang>/
│   ├── build_oxt.sh <lang> <plat>  # staging + zip -> dist/voice-dictation-<lang>-<plat>.oxt
│   └── _pack.py                    # token substitution + portable zip
├── build/                          # [generated] deps, models, staging (not versioned)
├── dist/                           # [generated] the .oxt files (not versioned)
└── src/                            # <-- becomes the root of the .oxt archive
    ├── description.xml             # extension metadata
    ├── Addons.xcu                  # toolbar button
    ├── ProtocolHandler.xcu         # routes button click to Python component
    ├── dettatura.py                # UNO component + Vosk engine + lockfile
    ├── trasformazione.py           # post-processing: punctuation + numbers
    ├── META-INF/manifest.xml
    ├── descriptions/               # text shown in Extension Manager
    └── icons/                      # microphone icons (16px, 26px) + extension icon
```

---

## Build (for developers)

Requirements: `bash`, `python3` + `pip`, `curl`. No `zip`/`unzip` needed (Python handles the zip for cross-platform compatibility).

### Local build (one language/platform)

```bash
make all LANG=en PLATFORM=linux_x86_64   # -> dist/voice-dictation-en-linux_x86_64.oxt
make oxt LANG=it                         # reuse already downloaded deps/model
```

Variables: `LANG=it|en` (default `it`), `PLATFORM=linux_x86_64|windows_x86_64|macos_aarch64` (default `linux_x86_64`).

### All platforms (release, via GitHub Actions)

Native wheels must be built on each OS — impossible from a single machine. The CI handles this. Just push a tag:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

The workflow builds on `ubuntu` / `windows` / `macos`, for both `it` and `en`, and attaches the **6 oxt files** to a GitHub Release.

---

## Something not working?

Logs are in `<tmp>/voice-dictation-logs/`, one file per language (`voice_dictation_it.log`, `voice_dictation_en.log`). Open them manually. The config file for each language is also there: `voice_dictation_<lang>.cfg.json`.

Config flags: `numeri`, `punteggiatura`, `comandi`, `verbose`, `debug`, `verbose-logging`.

Most common cause of silence: **microphone muted, volume at 0, or missing permissions**.

- 🪟 [Troubleshooting on Windows](docs/TROUBLESHOOTING_WINDOWS.md)
- 🐧 [Troubleshooting on Linux](docs/TROUBLESHOOTING_LINUX.md)

---

## License

[MIT](LICENSE).

Vosk is distributed under the Apache 2.0 license. Acoustic models have their own licenses — check the Vosk website before redistributing.
