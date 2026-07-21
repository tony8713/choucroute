"""Acoustic decoupling foam gasket — laser-cut ring for Laurent.

A flat annular ring cut from foam. It is the ONLY load path between the
reSpeaker stock case and the mic cup: the case rests on this ring, radial
clearance to the cup wall leaves no rigid coupling, so chassis/fan vibration
does not reach the mic array.

Outputs a 2D DXF (laser cut layout). Dimensions are pulled from earbox_v1 so
the gasket and the cup always agree — change dims there, regenerate both.
"""

from build123d import BuildSketch, Circle, Mode, export_dxf

import earbox_v1 as E

# Ring bearing surface: outer edge sits at the cup inner wall, inner edge opens
# a clear window under the mics.
GASKET_OUTER_DIA = E.CUP_INNER_DIA          # ~ case diameter, sits in the cup
GASKET_INNER_DIA = E.FOAM_SEAT_INNER_DIA    # open window under the mics
GASKET_THICKNESS = E.FOAM_THICKNESS         # foam stock thickness (see README)


def gen_dxf():
    with BuildSketch() as ring:
        Circle(GASKET_OUTER_DIA / 2)
        Circle(GASKET_INNER_DIA / 2, mode=Mode.SUBTRACT)
    return ring.sketch


if __name__ == "__main__":
    sk = gen_dxf()
    export_dxf(sk, "foam_gasket.dxf")
    print(
        f"wrote foam_gasket.dxf  OD={GASKET_OUTER_DIA:.1f} "
        f"ID={GASKET_INNER_DIA:.1f} thick={GASKET_THICKNESS:.1f} mm"
    )
