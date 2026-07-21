"""earbox founder-unit enclosure — v2 ("le monolithe").

Laurent rejected v1 as "batiment antique" (too temple-like). v2 design
language, per Laurent:
  - VERTICAL monolith: tall, slim silhouette (not a squat tower).
  - Sommet tronque sur deux aretes: the top is truncated / bevelled on two
    opposite edges (a chiselled crown), not a flat lid.
  - Ventilation = a mesh of small ROUNDED TRIANGLES (not slots).
Everything else carries over from v1: stock reSpeaker case in a foam-decoupled
cup at the top, SOLID deck between chambers, Orin below with real airflow
(triangle-mesh floor intake + high triangle-mesh exhaust), I/O windows, mute
hole, external LED band, external 60 W barrel PSU (confirmed by Laurent).

Component dimensions are imported from earbox_v1 (single source of truth) and
still tagged VERIFIED / UNVERIFIED there; Laurent's caliper values are still
pending — do NOT block on them, just re-run when they land.

Coordinate convention: origin at the monolith footprint centre, floor at z=0,
+Z up. Two printed parts: `mono_base` (tall vented body, prints upright, open
top) and `mono_crown` (truncated cup block, prints deck-down).
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
    GridLocations,
    Location,
    Locations,
    Keep,
    Mode,
    Plane,
    Pos,
    RegularPolygon,
    extrude,
    fillet,
    split,
)

import earbox_v1 as E

# ---------------------------------------------------------------------------
# v2-specific parameters (all one-line adjustable)
# ---------------------------------------------------------------------------
WALL = E.WALL              # 3.0 mm
DECK = E.DECK              # 3.0 mm solid divider (isolates fan noise)

# --- Openability + FDM fit (Laurent, 2am print rule): 0.75 mm on ALL fits ---
# The crown lifts straight off the base (see joint below). Everything is a
# generous slip/pry fit, shimmable with foam; nothing captive.
FIT = 0.75                 # universal FDM clearance on every mating fit (mm)
JOINT_FRAME = 7.0          # solid frame ring around the cup for the joint + bevel
JOINT_WALL = 3.0           # spigot wall thickness (mm)
JOINT_H = 10.0             # spigot engagement height (mm)
SPIGOT_OVERLAP = 1.0       # spigot bite into the wall so it fuses (mm)

# Footprint is bounded below by BOTH the Orin board and the (round) mic cup.
# The cased reSpeaker cup drives it; we add a joint frame so there is real wall
# for the pry-able joint and the two-edge bevel, then win "vertical" via HEIGHT.
FOOT_X = max(E.ORIN_LEN + 2 * E.ORIN_PCB_CLEAR + 2 * WALL,
             E.CUP_OUTER_DIA + 2 * JOINT_FRAME)
FOOT_Y = max(E.ORIN_WID + 2 * E.ORIN_PCB_CLEAR + 2 * WALL,
             E.CUP_OUTER_DIA + 2 * JOINT_FRAME)
BODY_FILLET = 4.0          # rounded vertical edges (monolith softness)

# Vertical proportion. Orin chamber + a tall exhaust plenum/chimney above it.
ORIN_CHAMBER_H = E.ORIN_LIFT + E.ORIN_HEIGHT + E.ORIN_TOP_CLEAR   # ~42 mm
PLENUM_H = 120.0           # tall chimney above the Orin -> the monolith body
MONO_BODY_H = ORIN_CHAMBER_H + PLENUM_H                          # ~162 mm

# Truncated crown (the mic block on top).
CROWN_H = 22.0             # crown block height (mm)
CROWN_CHAMFER = 8.0        # two-edge truncation depth (45 deg) on the top

# Triangle-mesh ventilation (rounded triangles, tessellated up+down).
TRI_SIDE = 11.0            # triangle edge length (mm)
TRI_GAP = 4.0             # web between triangles (>= ~3 mm for strength/print)
TRI_CORNER_R = 1.3        # corner rounding (mm)

# ---------------------------------------------------------------------------
# Derived
# ---------------------------------------------------------------------------
INNER_X = FOOT_X - 2 * WALL
INNER_Y = FOOT_Y - 2 * WALL
TRI_H = TRI_SIDE * math.sqrt(3) / 2.0
PITCH_X = TRI_SIDE + TRI_GAP
PITCH_Y = TRI_H + TRI_GAP


def _rounded_tri_field(w, h):
    """Sketch: a tessellated field of rounded triangles filling ~(w x h).

    Up-triangles on a grid plus down-triangles offset by half a cell -> a
    proper triangular mesh. Call inside an active BuildSketch context.
    """
    nx = max(1, int(w // PITCH_X))
    ny = max(1, int(h // PITCH_Y))
    r = TRI_SIDE / math.sqrt(3)  # circumradius from side length
    with Locations(Pos(0, 0)):
        with GridLocations(PITCH_X, PITCH_Y, nx, ny):
            RegularPolygon(r, 3, rotation=-90)          # pointing up
    with Locations(Pos(PITCH_X / 2, 0)):
        with GridLocations(PITCH_X, PITCH_Y, max(1, nx - 1), ny):
            RegularPolygon(r, 3, rotation=90)           # pointing down


def _cut_tri_panel(plane, w, h):
    """Cut a rounded-triangle mesh through a wall on `plane`. Active BuildPart."""
    with BuildSketch(plane) as sk:
        _rounded_tri_field(w, h)
        fillet(sk.vertices(), TRI_CORNER_R)
    extrude(sk.sketch, amount=WALL * 2, both=True, mode=Mode.SUBTRACT)


def _mono_base():
    """Tall vented monolith body holding the Orin. Prints upright, open top."""
    with BuildPart() as base:
        Box(FOOT_X, FOOT_Y, MONO_BODY_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        fillet(base.edges().filter_by(Axis.Z), BODY_FILLET)
        # hollow (open top)
        with Locations(Pos(0, 0, WALL)):
            Box(INNER_X, INNER_Y, MONO_BODY_H,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        # standoffs lift the Orin off the floor (underside airflow)
        with Locations(Pos(0, 0, WALL)):
            with GridLocations(E.ORIN_LEN - 16, E.ORIN_WID - 16, 2, 2):
                Box(7, 7, E.ORIN_LIFT,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- intake: triangle mesh in the floor ---
        _cut_tri_panel(Plane((0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, 0, 1)),
                       INNER_X - 12, INNER_Y - 12)

        # --- exhaust + body texture: triangle mesh high on all four walls ---
        panel_h = PLENUM_H - 20
        panel_zc = ORIN_CHAMBER_H + panel_h / 2 + 6
        # +Y and -Y long walls
        for ny in (1, -1):
            _cut_tri_panel(
                Plane((0, ny * FOOT_Y / 2, panel_zc),
                      x_dir=(1, 0, 0), z_dir=(0, ny, 0)),
                FOOT_X - 22, panel_h)
        # +X and -X short walls
        for nx in (1, -1):
            _cut_tri_panel(
                Plane((nx * FOOT_X / 2, 0, panel_zc),
                      x_dir=(0, 1, 0), z_dir=(nx, 0, 0)),
                FOOT_Y - 22, panel_h)

        # --- I/O windows on the +Y long wall, low (Orin I/O edge) ---
        yw = FOOT_Y / 2
        z0 = WALL + E.ORIN_LIFT + 2
        rect_ports = [
            (-42, E.PORT_DP_W, E.PORT_DP_H),
            (-22, E.PORT_USB_W, E.PORT_USB_H),
            (-4, E.PORT_USB_W, E.PORT_USB_H),
            (15, E.PORT_RJ45_W, E.PORT_RJ45_H),
            (31, E.PORT_USBC_W, E.PORT_USBC_H),
        ]
        for xoff, w, h in rect_ports:
            with Locations(Pos(xoff, yw, z0 + h / 2)):
                Box(w, WALL * 3, h,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT)
        with Locations(Location((43, yw, z0 + E.PORT_BARREL_D / 2), (90, 0, 0))):
            Cylinder(E.PORT_BARREL_D / 2, WALL * 3,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # --- locating spigot: upstanding rib the crown drops over (pry fit) ---
        # Crown lifts straight up off this; nothing captive. 0.75 mm slip fit.
        with Locations(Pos(0, 0, MONO_BODY_H - 1)):
            Box(INNER_X + 2 * SPIGOT_OVERLAP, INNER_Y + 2 * SPIGOT_OVERLAP,
                JOINT_H + 1,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
            Box(INNER_X - 2 * JOINT_WALL, INNER_Y - 2 * JOINT_WALL,
                (JOINT_H + 1) * 3,
                align=(Align.CENTER, Align.CENTER, Align.CENTER),
                mode=Mode.SUBTRACT)

        # --- cable pass-through at the top rim (USB up to the mic cup) ---
        with Locations(Pos(0, 0, MONO_BODY_H - 1)):
            Cylinder(E.CABLE_DIA / 2, WALL * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

    part = base.part
    part.label = "mono_base"
    return part


def _mono_crown():
    """Truncated-crown mic block: cup + two-edge bevel. Prints deck-down."""
    with BuildPart() as crown:
        Box(FOOT_X, FOOT_Y, CROWN_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        fillet(crown.edges().filter_by(Axis.Z), BODY_FILLET)

        # sommet tronque sur deux aretes: truncate the two top edges || X with
        # 45-deg planar cuts (robust vs OCC chamfer at the rounded corners).
        split(bisect_by=Plane((0, FOOT_Y / 2, CROWN_H - CROWN_CHAMFER),
                              z_dir=(0, 1, 1)), keep=Keep.BOTTOM)
        split(bisect_by=Plane((0, -FOOT_Y / 2, CROWN_H - CROWN_CHAMFER),
                              z_dir=(0, -1, 1)), keep=Keep.BOTTOM)

        # receiving groove in the bottom for the base spigot (0.75 mm pry fit).
        # Cut on the solid block (before boring the cup): subtract outer, refill
        # inner -> a ring groove that lives entirely in the joint frame.
        gd = JOINT_H + FIT
        with Locations(Pos(0, 0, -0.5)):
            Box(INNER_X + 2 * SPIGOT_OVERLAP + FIT,
                INNER_Y + 2 * SPIGOT_OVERLAP + FIT, gd + 0.5,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
            Box(INNER_X - 2 * JOINT_WALL - FIT, INNER_Y - 2 * JOINT_WALL - FIT,
                gd + 0.5,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.ADD)

        # bore the reSpeaker cup from the top; leave DECK solid at the bottom
        cup_depth = CROWN_H - DECK
        with Locations(Pos(0, 0, CROWN_H)):
            Cylinder(E.CUP_INNER_DIA / 2, cup_depth,
                     align=(Align.CENTER, Align.CENTER, Align.MAX),
                     mode=Mode.SUBTRACT)
        # foam gasket seat: shallow blind recess at the cup floor
        with Locations(Pos(0, 0, DECK)):
            Cylinder(E.CUP_INNER_DIA / 2, E.FOAM_THICKNESS,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)

        # external LED band near the rim (trust interface)
        band_z = CROWN_H - E.LED_RING_CHANNEL_W - 2.0
        with Locations(Pos(0, 0, band_z)):
            Cylinder(E.CUP_OUTER_DIA / 2, E.LED_RING_CHANNEL_W,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
            Cylinder(E.CUP_OUTER_DIA / 2 - E.LED_RING_CHANNEL_D,
                     E.LED_RING_CHANNEL_W,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.ADD)

        # mute switch hole through a wall into the cup (privacy)
        with Locations(Location((FOOT_X / 2, 0, DECK + 6), (0, 90, 0))):
            Cylinder(E.MUTE_HOLE_DIA / 2, WALL * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # cable channel down through the deck into the base
        with Locations(Pos(0, 0, 0)):
            Cylinder(E.CABLE_DIA / 2, DECK * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

    part = crown.part
    part.label = "mono_crown"
    return part


def gen_step():
    base = _mono_base()
    crown = _mono_crown()
    crown.locate(Location((0, 0, MONO_BODY_H)))
    return Compound(label="earbox_v2", children=[base, crown])


if __name__ == "__main__":
    from build123d import export_step
    export_step(gen_step(), "earbox_v2.step")
    print("wrote earbox_v2.step")
