"""earbox founder-unit enclosure — v3 ("le monolithe vertical").

Laurent's literal v3 spec (v2's mesh rendered as hearts/stars because it used
RegularPolygon + filleting of overlapping interleaved triangles; v3 builds each
triangle as an explicit 3-point polygon on a non-touching quincunx grid):

  - Rectangular box, LARGEST dimension = height (tall + narrow).
  - Shell 3 mm.
  - Top truncated DIAGONALLY with TWO slightly offset cuts (deux outils
    legerement decales) -> a stepped/faceted summit.
  - Ventilation: a 5x5 quincunx grid of rounded-corner triangles FACING THE
    ORIN FAN, plus a triangle mesh on the UNDERSIDE. No other wall vents.
  - Triangles EN QUINCONCE (staggered rows, half-pitch offset, alternating
    up/down), with webs so they never touch.
  - Stands on 4 TRIANGULAR feet, 5 mm high.
  - "earbox" DEBOSSED 2 mm, monospace.

Kept: two-part easy-open split (no captive parts), reSpeaker case 107x17
VERIFIED with 0.75 mm clearances, foam-decoupled seat, Orin 30 mm conservative,
mute hole 16 mm, support-light print orientation.

Coordinates: origin at footprint centre, z=0 at the box floor underside (feet
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
    Keep,
    Location,
    Locations,
    Mode,
    Plane,
    Polygon,
    Pos,
    Text,
    extrude,
    fillet,
    split,
)

import earbox_v1 as E

# ---------------------------------------------------------------------------
# Parameters (one-line adjustable)
# ---------------------------------------------------------------------------
WALL = 3.0
FIT = 0.75                 # FDM clearance on every mating fit (Laurent rule)

# Footprint driven by the round cased reSpeaker (narrowest that fits it).
FOOT = E.CUP_OUTER_DIA     # = 107 case + 2*0.75 fit + 2*3 wall = 114.5 mm

# Vertical stack so HEIGHT is the largest dimension.
FLOOR = WALL
FEET_H = 5.0
ORIN_CHAMBER_H = E.ORIN_LIFT + E.ORIN_HEIGHT + E.ORIN_TOP_CLEAR   # ~42 mm
PLENUM_H = 135.0
CROWN_H = 26.0
SPLIT_Z = FLOOR + ORIN_CHAMBER_H + PLENUM_H    # base/crown parting plane
TOTAL_H = SPLIT_Z + CROWN_H                     # ~206 mm (+5 feet)

# Corner-post locating joint (pry-open, nothing captive). Posts live in the
# square corners (outside the round cup), so no joint frame is needed.
POST = 8.0                 # post cross-section (mm)
POST_H = 10.0              # engagement height (mm)
POST_OVERLAP = 1.0         # post bite into the two corner walls so it fuses (mm)

# Truncated summit: a DIAGONAL truncation made of two same-side facets at
# slightly different angles/positions (deux outils legerement decales) -> a
# stepped/faceted diagonal summit sloping toward +Y.
SUMMIT_A_TILT = 0.5        # main diagonal facet slope
SUMMIT_A_Y = -8.0          # where the main cut meets the top
SUMMIT_B_TILT = 0.95       # second, steeper facet
SUMMIT_B_Y = 16.0          # offset of the second cut (the "decalage")
SUMMIT_B_DROP = 3.0        # second cut starts slightly lower -> a step/crease

# Triangle vents (explicit polygons, quincunx, webbed so they never touch).
FAN_TRI_SIDE = 9.0
FAN_TRI_GAP = 4.0
UND_TRI_SIDE = 9.0
UND_TRI_GAP = 4.5
TRI_R = 1.3                # corner rounding

MUTE_HOLE_DIA = 16.0       # Laurent default

# ---------------------------------------------------------------------------
# Derived
# ---------------------------------------------------------------------------
INNER = FOOT - 2 * WALL
CUP_ID = E.CUP_INNER_DIA
CUP_OD = E.CUP_OUTER_DIA
POST_C = INNER / 2 - POST / 2 + POST_OVERLAP   # corner post centre (fuses to walls)


def _tri_pts(cx, cy, side, up):
    h = side * math.sqrt(3) / 2.0
    if up:
        return [(cx - side / 2, cy - h / 3), (cx + side / 2, cy - h / 3),
                (cx, cy + 2 * h / 3)]
    return [(cx - side / 2, cy + h / 3), (cx + side / 2, cy + h / 3),
            (cx, cy - 2 * h / 3)]


def _quincunx_field(nx, ny, side, gap):
    """Add a staggered (en quinconce) field of rounded triangles to the active
    BuildSketch. Alternating up/down, odd rows shifted half a pitch, webbed so
    triangles never touch (touching is what turned v2 into hearts/stars)."""
    h = side * math.sqrt(3) / 2.0
    pitch_x = side + gap
    pitch_y = h + gap
    x0 = -(nx - 1) * pitch_x / 2.0
    y0 = -(ny - 1) * pitch_y / 2.0
    for j in range(ny):
        xshift = (pitch_x / 2.0) if (j % 2) else 0.0
        for i in range(nx):
            up = ((i + j) % 2 == 0)
            cx = x0 + i * pitch_x + xshift
            cy = y0 + j * pitch_y
            Polygon(*_tri_pts(cx, cy, side, up), align=None)


def _cut_quincunx(plane, nx, ny, side, gap):
    with BuildSketch(plane) as sk:
        _quincunx_field(nx, ny, side, gap)
        fillet(sk.vertices(), TRI_R)
    extrude(sk.sketch, amount=WALL * 2, both=True, mode=Mode.SUBTRACT)


def _base():
    with BuildPart() as base:
        Box(FOOT, FOOT, SPLIT_Z, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # cavity (open top)
        with Locations(Pos(0, 0, FLOOR)):
            Box(INNER, INNER, SPLIT_Z, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        # Orin standoffs
        with Locations(Pos(0, 0, FLOOR)):
            with Locations(*[Pos(sx * (E.ORIN_LEN / 2 - 6),
                                 sy * (E.ORIN_WID / 2 - 6), 0)
                             for sx in (1, -1) for sy in (1, -1)]):
                Box(7, 7, E.ORIN_LIFT, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # 4 triangular feet, 5 mm high, under the corners
        for sx in (1, -1):
            for sy in (1, -1):
                c = FOOT / 2 - 4
                pts = [(sx * c, sy * c),
                       (sx * (c - 16), sy * c),
                       (sx * c, sy * (c - 16))]
                with BuildSketch(Plane.XY) as ft:
                    Polygon(*pts, align=None)
                extrude(ft.sketch, amount=-FEET_H, mode=Mode.ADD)

        # --- underside triangle mesh (intake), quincunx through the floor ---
        _cut_quincunx(Plane((0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, 0, 1)),
                      7, 7, UND_TRI_SIDE, UND_TRI_GAP)

        # --- 5x5 quincunx facing the Orin fan, on the -X wall ---
        fan_zc = FLOOR + ORIN_CHAMBER_H / 2 + 18
        _cut_quincunx(Plane((-FOOT / 2, 0, fan_zc), x_dir=(0, 1, 0),
                            z_dir=(-1, 0, 0)), 5, 5, FAN_TRI_SIDE, FAN_TRI_GAP)

        # --- I/O windows on the +Y wall, low (functional; not a "vent") ---
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

        # --- "earbox" debossed 2 mm, monospace, on the -Y wall ---
        with BuildSketch(Plane((0, -FOOT / 2, SPLIT_Z * 0.55),
                               x_dir=(-1, 0, 0), z_dir=(0, -1, 0))) as tx:
            Text("earbox", font_size=13, font="Menlo")
        extrude(tx.sketch, amount=-2.0, mode=Mode.SUBTRACT)

        # --- locating posts at the 4 corners (crown drops over -> pries off) ---
        # start 2 mm below the parting plane and overlap the walls so each post
        # fuses solidly into its corner (no floating solids).
        for sx in (1, -1):
            for sy in (1, -1):
                with Locations(Pos(sx * POST_C, sy * POST_C, SPLIT_Z - 2)):
                    Box(POST, POST, POST_H + 2,
                        align=(Align.CENTER, Align.CENTER, Align.MIN))

    part = base.part
    part.label = "mono_base"
    return part


def _crown():
    with BuildPart() as crown:
        Box(FOOT, FOOT, CROWN_H, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # blind holes for the base posts (0.75 slip fit), open downward
        for sx in (1, -1):
            for sy in (1, -1):
                with Locations(Pos(sx * POST_C, sy * POST_C, -0.5)):
                    Box(POST + FIT, POST + FIT, POST_H + FIT + 0.5,
                        align=(Align.CENTER, Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT)

        # bore the reSpeaker cup from the top; DECK stays solid at the bottom
        with Locations(Pos(0, 0, CROWN_H)):
            Cylinder(CUP_ID / 2, CROWN_H - E.DECK,
                     align=(Align.CENTER, Align.CENTER, Align.MAX),
                     mode=Mode.SUBTRACT)
        # foam gasket seat (blind recess at the cup floor)
        with Locations(Pos(0, 0, E.DECK)):
            Cylinder(CUP_ID / 2, E.FOAM_THICKNESS,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)

        # mute switch hole through the +X wall into the cup
        with Locations(Location((FOOT / 2, 0, E.DECK + 7), (0, 90, 0))):
            Cylinder(MUTE_HOLE_DIA / 2, WALL * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # cable channel through the deck into the base
        with Locations(Pos(0, 0, 0)):
            Cylinder(E.CABLE_DIA / 2, E.DECK * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # --- truncated summit: two same-side offset diagonal facets ---
        split(bisect_by=Plane((0, SUMMIT_A_Y, CROWN_H),
                              z_dir=(0, SUMMIT_A_TILT, 1)), keep=Keep.BOTTOM)
        split(bisect_by=Plane((0, SUMMIT_B_Y, CROWN_H - SUMMIT_B_DROP),
                              z_dir=(0, SUMMIT_B_TILT, 1)), keep=Keep.BOTTOM)

    part = crown.part
    part.label = "mono_crown"
    return part


def gen_step():
    base = _base()
    crown = _crown()
    crown.locate(Location((0, 0, SPLIT_Z)))
    return Compound(label="earbox_v3", children=[base, crown])


if __name__ == "__main__":
    from build123d import export_step
    export_step(gen_step(), "earbox_v3.step")
    print("wrote earbox_v3.step")
