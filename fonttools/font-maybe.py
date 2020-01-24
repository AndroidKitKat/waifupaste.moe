#!/usr/bin/env python3

import sys
import fontforge

if len(sys.argv) == 4:
    font = fontforge.open(sys.argv[1])

    f = open(sys.argv[2], "r")

    for i in f.read():
        font.selection[ord(i)] = True
    f.close()

    font.selection.invert()

    for i in font.selection.byGlyphs:
        font.removeGlyph(i)

    font.generate(sys.argv[3])


