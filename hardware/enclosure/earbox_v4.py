"""earbox founder-unit enclosure — v4 ("le cube").

Laurent's v4 spec (from v3):
  1. Debossed "earbox" text was UPSIDE DOWN -> fixed (upright + readable when
     the cube sits on its feet).
  2. PERFECT CUBE -> drop the vertical stretch; side = as small as the 107 case
     allows while fitting Orin + plenum (= 114.5 mm).
  3. DROP the diagonal summit -> flat top.
  4. Triangles packed CLOSER (tighter pitch), same rounded quinconce pattern:
     5x5 facing the Orin fan + underside mesh.
  5. Internal reSpeaker USB cable channel routed along one vertical corner
     (arete) from the Orin chamber up into the crown cup.

Kept: two-part pry-open split (nothing captive), case 107x17 VERIFIED + 0.75
fits, foam-decoupled seat, mute hole 16 mm, 4 triangular feet 5 mm, 3 mm shell,
debossed monospace text 2 mm, support-light print orientation.

Triangles are explicit 3-point polygons with corner fillets on a non-touching
quincunx grid (NOT RegularPolygon/glyphs -> that was the v2 hearts/stars bug).
Verify by rendering the exported STL, not the sketch.

Coordinates: origin at footprint centre, z=0 at the cube floor underside (feet
extend to z=-5). +Z up.
"""

import math

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Cylinder,
    Location,
    Locations,
    Mode,
    Plane,
    Polygon,
    Pos,
    Text,
    extrude,
    fillet,
)

import earbox_v1 as E

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
WALL = 3.0
FIT = 0.75

# Perfect cube: side driven by the round cased reSpeaker (smallest that fits).
FOOT = E.CUP_OUTER_DIA          # 107 + 2*0.75 + 2*3 = 114.5 mm
CUBE = FOOT                     # perfect cube edge

FLOOR = WALL
FEET_H = 5.0
ORIN_CHAMBER_H = E.ORIN_LIFT + E.ORIN_HEIGHT + E.ORIN_TOP_CLEAR   # ~42 mm
CROWN_H = 26.0
SPLIT_Z = CUBE - CROWN_H        # base/crown parting plane (= 88.5)

# Corner-post locating joint (pry-open, nothing captive).
POST = 8.0
POST_H = 10.0
POST_OVERLAP = 1.0
POST_C = FOOT / 2 - WALL - POST / 2 + POST_OVERLAP   # inner corner, fused to walls

# Triangle vents (explicit polygons, quincunx, packed CLOSE, webbed).
FAN_TRI_SIDE = 9.0
FAN_TRI_GAP = 2.5
UND_TRI_SIDE = 8.0
UND_TRI_GAP = 2.5
TRI_R = 1.2

MUTE_HOLE_DIA = 16.0

# No cable channel/clips. The reSpeaker case is seated ROTATED 45 deg so its USB
# connector points into the box interior toward the (+X,+Y) corner; the cable
# just drops inside to the Orin. We only cut a connector-clearance opening at
# that corner (through the cup wall + down through the deck) and a rim marker so
# the assembler knows how to orient the case.
CONN_W = 15.0                   # connector-clearance opening width (mm)
CONN_H = 12.0                   # opening height above the deck (mm)
MARKER_W = 3.0                  # rim orientation-notch width (mm)

# ---------------------------------------------------------------------------
# Derived
# ---------------------------------------------------------------------------
INNER = FOOT - 2 * WALL
CUP_ID = E.CUP_INNER_DIA
CORNER = INNER / 2              # inner-corner coordinate on each axis
CABLE_H = SPLIT_Z - FLOOR


def _tri_pts(cx, cy, side, up):
    h = side * math.sqrt(3) / 2.0
    if up:
        return [(cx - side / 2, cy - h / 3), (cx + side / 2, cy - h / 3),
                (cx, cy + 2 * h / 3)]
    return [(cx - side / 2, cy + h / 3), (cx + side / 2, cy + h / 3),
            (cx, cy - 2 * h / 3)]


def _quincunx_field(nx, ny, side, gap):
    h = side * math.sqrt(3) / 2.0
    pitch_x = side + gap
    pitch_y = h + gap
    x0 = -(nx - 1) * pitch_x / 2.0
    y0 = -(ny - 1) * pitch_y / 2.0
    for j in range(ny):
        xshift = (pitch_x / 2.0) if (j % 2) else 0.0
        for i in range(nx):
            up = ((i + j) % 2 == 0)
            Polygon(*_tri_pts(x0 + i * pitch_x + xshift, y0 + j * pitch_y, side, up),
                    align=None)


def _cut_quincunx(plane, nx, ny, side, gap):
    with BuildSketch(plane) as sk:
        _quincunx_field(nx, ny, side, gap)
        fillet(sk.vertices(), TRI_R)
    extrude(sk.sketch, amount=WALL * 2, both=True, mode=Mode.SUBTRACT)


def _base():
    with BuildPart() as base:
        Box(CUBE, CUBE, SPLIT_Z, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(Pos(0, 0, FLOOR)):
            Box(INNER, INNER, SPLIT_Z, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        # Orin standoffs
        with Locations(*[Pos(sx * (E.ORIN_LEN / 2 - 6), sy * (E.ORIN_WID / 2 - 6),
                             FLOOR) for sx in (1, -1) for sy in (1, -1)]):
            Box(7, 7, E.ORIN_LIFT, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # 4 triangular feet, 5 mm high, under the corners
        for sx in (1, -1):
            for sy in (1, -1):
                c = FOOT / 2 - 4
                with BuildSketch(Plane.XY) as ft:
                    Polygon((sx * c, sy * c), (sx * (c - 16), sy * c),
                            (sx * c, sy * (c - 16)), align=None)
                extrude(ft.sketch, amount=-FEET_H, mode=Mode.ADD)

        # --- underside triangle mesh (intake), packed quincunx ---
        _cut_quincunx(Plane((0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, 0, 1)),
                      9, 9, UND_TRI_SIDE, UND_TRI_GAP)

        # --- 5x5 quincunx facing the Orin fan (-X wall) ---
        fan_zc = FLOOR + ORIN_CHAMBER_H / 2 + 8
        _cut_quincunx(Plane((-FOOT / 2, 0, fan_zc), x_dir=(0, 1, 0),
                            z_dir=(-1, 0, 0)), 5, 5, FAN_TRI_SIDE, FAN_TRI_GAP)

        # --- I/O windows on the +Y wall, low (functional) ---
        yw = FOOT / 2
        z0 = FLOOR + E.ORIN_LIFT + 2
        for xoff, w, h in [(-40, E.PORT_DP_W, E.PORT_DP_H),
                           (-20, E.PORT_USB_W, E.PORT_USB_H),
                           (-2, E.PORT_USB_W, E.PORT_USB_H),
                           (16, E.PORT_RJ45_W, E.PORT_RJ45_H),
                           (32, E.PORT_USBC_W, E.PORT_USBC_H)]:
            with Locations(Pos(xoff, yw, z0 + h / 2)):
                Box(w, WALL * 3, h, align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT)
        with Locations(Location((43, yw, z0 + E.PORT_BARREL_D / 2), (90, 0, 0))):
            Cylinder(E.PORT_BARREL_D / 2, WALL * 3,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # --- "earbox" debossed 2 mm, monospace, UPRIGHT + readable, -Y wall ---
        # x_dir +X and z_dir -Y (outward) -> local Y = +Z (up), local X = +X.
        with BuildSketch(Plane((0, -FOOT / 2, SPLIT_Z * 0.5),
                               x_dir=(1, 0, 0), z_dir=(0, -1, 0))) as tx:
            Text("earbox", font_size=13, font="Menlo")
        extrude(tx.sketch, amount=-2.0, mode=Mode.SUBTRACT)

        # --- corner locating posts ---
        for sx in (1, -1):
            for sy in (1, -1):
                with Locations(Pos(sx * POST_C, sy * POST_C, SPLIT_Z - 2)):
                    Box(POST, POST, POST_H + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))

    part = base.part
    part.label = "mono_base"
    return part


def _crown():
    with BuildPart() as crown:
        Box(CUBE, CUBE, CROWN_H, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # blind post holes (0.75 slip fit), open downward
        for sx in (1, -1):
            for sy in (1, -1):
                with Locations(Pos(sx * POST_C, sy * POST_C, -0.5)):
                    Box(POST + FIT, POST + FIT, POST_H + FIT + 0.5,
                        align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # bore the reSpeaker cup from the (flat) top; DECK solid at the bottom
        with Locations(Pos(0, 0, CROWN_H)):
            Cylinder(CUP_ID / 2, CROWN_H - E.DECK,
                     align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        with Locations(Pos(0, 0, E.DECK)):
            Cylinder(CUP_ID / 2, E.FOAM_THICKNESS,
                     align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # mute switch hole through the +X wall into the cup
        with Locations(Location((FOOT / 2, 0, E.DECK + 7), (0, 90, 0))):
            Cylinder(MUTE_HOLE_DIA / 2, WALL * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

        # connector-clearance opening at the (+X,+Y) corner (45 deg): the case
        # is seated ROTATED 45 deg with its USB pointing here; this notches the
        # cup wall and opens the deck below so the plug clears and the cable
        # drops straight into the base. No channel, no clips.
        cc = (CUP_ID / 2) / math.sqrt(2.0)     # cup-wall point on the diagonal
        with Locations(Location((cc, cc, -1), (0, 0, 45))):
            Box(CONN_W, 22, E.DECK + CONN_H + 1,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # orientation marker: shallow triangle debossed into the flat top,
        # pointing at the corner so the case is seated the right way.
        mk = (CUP_ID / 2 + 3) / math.sqrt(2.0)
        with BuildSketch(Plane((mk, mk, CROWN_H), x_dir=(1, -1, 0),
                               z_dir=(0, 0, 1))) as mkr:
            Polygon((-4, -2.3), (4, -2.3), (0, 2.3), align=None)
        extrude(mkr.sketch, amount=-1.5, mode=Mode.SUBTRACT)

    part = crown.part
    part.label = "mono_crown"
    return part


def gen_step():
    base = _base()
    crown = _crown()
    crown.locate(Location((0, 0, SPLIT_Z)))
    return Compound(label="earbox_v4", children=[base, crown])


if __name__ == "__main__":
    from build123d import export_step
    export_step(gen_step(), "earbox_v4.step")
    print("wrote earbox_v4.step")
