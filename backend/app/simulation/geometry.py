"""Canonical geography shared by scenario validation and the real road model."""
import math


def river_cells(layout="grid"):
    if layout == "grid":
        return {(x, y) for y in range(40) for x in range(18, 21)}
    return {(x, y) for y in range(40)
            for x in range(18 + round(3 * math.sin((y - 4) * math.pi / 20)),
                           21 + round(3 * math.sin((y - 4) * math.pi / 20)))}
