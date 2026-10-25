"""Original tabular pixel numerals for the game HUD (no borrowed glyph outlines).

Rebuild: uv run --no-project --with fonttools python frontend/art/last-warning/generate_digits.py
The checked-in TTF is a runtime asset; fontTools is only an authoring dependency.
"""
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


# Seven rows, five columns. In particular, 2 descends diagonally to a full base,
# while 5 has a full cap and an upright upper-left stem, distinct from S.
DIGITS = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
}


def glyph(rows):
    pen = TTGlyphPen(None)
    for row, pixels in enumerate(rows):
        column = 0
        while column < len(pixels):
            if pixels[column] == "0":
                column += 1
                continue
            start = column
            while column < len(pixels) and pixels[column] == "1":
                column += 1
            left, right = 68 + start * 90, 68 + column * 90
            bottom, top = (6 - row) * 90, (7 - row) * 90
            pen.moveTo((left, bottom))
            pen.lineTo((left, top))
            pen.lineTo((right, top))
            pen.lineTo((right, bottom))
            pen.closePath()
    return pen.glyph()


def main():
    names = [".notdef", *[f"digit{digit}" for digit in DIGITS]]
    font = FontBuilder(1000, isTTF=True)
    font.setupGlyphOrder(names)
    font.setupCharacterMap({ord(digit): f"digit{digit}" for digit in DIGITS})
    font.setupGlyf({".notdef": glyph([]), **{f"digit{d}": glyph(rows) for d, rows in DIGITS.items()}})
    # The narrow 1 starts one pixel farther right. Its side bearing must match
    # the outline's xMin; a shared bearing shifts that glyph left on screen.
    font.setupHorizontalMetrics({
        name: (586, font.font["glyf"][name].xMin if name != ".notdef" else 0)
        for name in names
    })
    # Match the existing display font's line metrics so the HUD does not jump.
    font.setupHorizontalHeader(ascent=920, descent=-280)
    font.setupNameTable({
        "familyName": "Last Warning Digits", "styleName": "Regular",
        "uniqueFontIdentifier": "LastWarningDigits-1.1", "fullName": "Last Warning Digits",
        "psName": "LastWarningDigits-Regular", "version": "Version 1.1",
        "copyright": "Original Last Warning project artwork, 2026.",
    })
    font.setupOS2(sTypoAscender=920, sTypoDescender=-280, usWinAscent=920,
                  usWinDescent=280, sxHeight=500, sCapHeight=700)
    font.setupPost(isFixedPitch=1)
    font.setupMaxp()
    # A stable build timestamp keeps regeneration reproducible.
    font.font["head"].created = font.font["head"].modified = 3875644800
    font.font.recalcTimestamp = False
    output = Path(__file__).resolve().parents[2] / "public/assets/fonts/LastWarningDigits.ttf"
    font.save(output)
    print(f"Saved {output.name}: {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
