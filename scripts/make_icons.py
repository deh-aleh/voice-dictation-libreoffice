#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera le icone PNG del pulsante (microfono) senza dipendenze esterne.

Produce in src/icons/:
  - mic_16.png          16x16  (toolbar standard)
  - mic_26.png          26x26  (HiDPI / barre grandi)
  - extension_icon.png  32x32  (Gestione estensioni)

Disegno: silhouette di microfono su sfondo trasparente. Lo stato on/off in
LibreOffice e' reso dal pulsante "premuto" (toggle), non da icone diverse.
"""
import os
import zlib
import struct

# Colore del microfono (slate scuro), opaco.
FG = (60, 64, 72, 255)
TRANSP = (0, 0, 0, 0)


def disegna_mic(size):
    """Restituisce una matrice RGBA (lista di righe di tuple) con un microfono."""
    s = size
    px = [[TRANSP for _ in range(s)] for _ in range(s)]

    cx = s / 2.0
    cap_w = s * 0.30          # larghezza capsula
    cap_top = s * 0.12
    cap_bot = s * 0.52
    cap_r = cap_w / 2.0

    arc_r = s * 0.26          # raggio archetto di supporto
    arc_cy = cap_bot
    stand_top = arc_cy + arc_r
    base_y = s * 0.86
    base_half = s * 0.18
    line_w = max(1.0, s * 0.07)

    for y in range(s):
        for x in range(s):
            fx, fy = x + 0.5, y + 0.5
            on = False

            # Capsula: rettangolo arrotondato (capsule) centrato in alto.
            if cap_top + cap_r <= fy <= cap_bot - cap_r:
                if abs(fx - cx) <= cap_r:
                    on = True
            # Calotte semicircolari sopra e sotto la capsula.
            for ccy in (cap_top + cap_r, cap_bot - cap_r):
                if (fx - cx) ** 2 + (fy - ccy) ** 2 <= cap_r ** 2:
                    on = True

            # Archetto: semianello sotto la capsula (solo meta' inferiore).
            d = ((fx - cx) ** 2 + (fy - arc_cy) ** 2) ** 0.5
            if fy >= arc_cy and abs(d - arc_r) <= line_w / 1.5:
                on = True

            # Stelo verticale.
            if stand_top - line_w <= fy <= base_y and abs(fx - cx) <= line_w / 2.0:
                on = True

            # Base orizzontale.
            if abs(fy - base_y) <= line_w / 2.0 and abs(fx - cx) <= base_half:
                on = True

            if on:
                px[y][x] = FG
    return px


def scrivi_png(path, px):
    """Serializza la matrice RGBA in un file PNG (solo stdlib)."""
    h = len(px)
    w = len(px[0])
    raw = bytearray()
    for row in px:
        raw.append(0)  # filtro 'None' per riga
        for (r, g, b, a) in row:
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit, RGBA
    idat = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "src", "icons")
    os.makedirs(out, exist_ok=True)
    for name, size in (("mic_16.png", 16), ("mic_26.png", 26), ("extension_icon.png", 32)):
        scrivi_png(os.path.join(out, name), disegna_mic(size))
        print("scritto", name)


if __name__ == "__main__":
    main()
