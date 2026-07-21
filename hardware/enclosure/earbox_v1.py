"""earbox founder-unit enclosure — v1 ("le boitier").

Two-chamber tower: NVIDIA Jetson Orin Nano Super dev kit in a vented lower
base, Seeed reSpeaker XVF3800 (kept in its STOCK retail case for v1) in an
acoustically-decoupled upper mic cup. USB cable channel between chambers.

Design intent, print notes and the foam-gasket spec live in README.md next to
this file. STEP is the primary artifact; STL is a printable sidecar.

=============================================================================
 CRITICAL DIMENSIONS — one-line adjustable. Each is tagged:
   [VERIFIED]   backed by an official datasheet / product page (see README)
   [UNVERIFIED] estimate or third-party value; Laurent to caliper-verify the
                real part before any print. reSpeaker case dims especially.
 Change a value here and re-run `scripts/step earbox_v1.py` to regenerate.
=============================================================================
"""

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Circle,
    Cylinder,
    GridLocations,
    Location,
    Locations,
    Mode,
    Plane,
    Pos,
    Rectangle,
    Compound,
    extrude,
    fillet,
)

# ---------------------------------------------------------------------------
# Jetson Orin Nano Super Developer Kit — lower chamber occupant
# ---------------------------------------------------------------------------
# Reference carrier board (P3768) footprint.
ORIN_LEN = 100.0          # [VERIFIED] board length (mm)
ORIN_WID = 79.0           # [VERIFIED] board width  (mm) — NVIDIA datasheet
# Full assembled stack height INCLUDING the stock heatsink + fan. Conflicting
# sources: NVIDIA datasheet says 21 mm "incl. feet, carrier, module, thermal
# solution"; jetsonhacks quotes 30 mm. We default CONSERVATIVE (larger) so the
# fan is never choked. If Laurent calipers ~21 mm, drop this to 21 and re-run.
ORIN_HEIGHT = 30.0        # [UNVERIFIED] full stack incl. fan (mm) — see README conflict
ORIN_PCB_CLEAR = 2.5      # clearance around the board in the base cavity (mm)
ORIN_LIFT = 4.0           # standoff lift off the floor for underside airflow (mm)
ORIN_TOP_CLEAR = 8.0      # air gap above the fan to the deck for exhaust (mm)

# ---------------------------------------------------------------------------
# Seeed reSpeaker XVF3800 USB 4-Mic Array — upper chamber occupant
# v1 keeps the STOCK retail case intact (mic geometry preserved). We hold the
# whole cased puck in a cup; we do NOT reproduce the bare-board mic pattern.
# NOTE: the bare PCB is ~99 mm round (NOT the ~70 mm from the brief). The cased
# retail puck (SKU p-6490) is therefore ~100 mm+; no official case dims exist.
# ---------------------------------------------------------------------------
RESPEAKER_PCB_DIA = 99.0     # [UNVERIFIED] bare PCB diameter (mm) — third-party (cnx)
RESPEAKER_CASE_DIA = 102.0   # [UNVERIFIED] stock case outer diameter (mm) — measure the p-6490 STEP
RESPEAKER_CASE_H = 20.0      # [UNVERIFIED] stock case height (mm) — measure the p-6490 STEP
RESPEAKER_RADIAL_CLEAR = 1.0 # radial clearance cup wall -> case (loose, decoupled)

# ---------------------------------------------------------------------------
# Acoustic decoupling — laser-cut foam gasket (Laurent supplies foam)
# The reSpeaker case rests ONLY on this foam ring; radial clearance to the cup
# wall means no rigid path from case to chassis. The seat is recessed by the
# foam thickness so the compressed foam sets the standoff.
# ---------------------------------------------------------------------------
FOAM_THICKNESS = 3.0         # [UNVERIFIED] laser-cut foam gasket thickness (mm) — Laurent to confirm
FOAM_RING_WIDTH = 6.0        # radial width of the foam ring bearing surface (mm)

# ---------------------------------------------------------------------------
# Enclosure global
# ---------------------------------------------------------------------------
WALL = 3.0                   # nominal wall thickness (mm)
FILLET = 2.0                 # cosmetic outer vertical fillet (mm)
DECK = 3.0                   # divider deck thickness between chambers (mm)
CABLE_DIA = 9.0              # USB cable channel diameter chamber-to-chamber (mm)

# ---- Port face cutouts (Orin I/O edge). Sizes are generous v1 windows. ----
# Along the ORIN_LEN edge. Heights measured from the board plane (z above lift).
PORT_BARREL_D = 9.0          # DC barrel jack window dia (mm)
PORT_USB_W, PORT_USB_H = 16.0, 17.0   # stacked USB-A double window
PORT_USBC_W, PORT_USBC_H = 11.0, 5.0
PORT_RJ45_W, PORT_RJ45_H = 17.0, 15.0
PORT_DP_W, PORT_DP_H = 20.0, 8.0

# ---- Vents ----
VENT_SLOT_W = 3.0
VENT_SLOT_L = 22.0
VENT_GAP = 3.0

# ---- Mute switch (privacy) & LED ring channel (future trust interface) ----
MUTE_HOLE_DIA = 7.0          # panel-mount toggle/tactile switch hole (mm)
# Shallow external band recessed around the cup near the top rim; a future LED
# ring (Fabien's trust interface) seats here. Depth stays < WALL so it never
# breaches the case cavity.
LED_RING_CHANNEL_W = 6.0     # vertical height of the LED band (mm)
LED_RING_CHANNEL_D = 1.5     # radial recess depth into the outer wall (mm)

# ---------------------------------------------------------------------------
# Derived
# ---------------------------------------------------------------------------
CUP_INNER_DIA = RESPEAKER_CASE_DIA + 2 * RESPEAKER_RADIAL_CLEAR
CUP_OUTER_DIA = CUP_INNER_DIA + 2 * WALL

# The cased mic puck (~110 mm) is wider than the bare Orin footprint (~90 mm),
# so we grow the base to fully support the puck. The extra interior around the
# board becomes an air plenum (helps, doesn't choke, the fan).
BASE_INNER_L = max(ORIN_LEN + 2 * ORIN_PCB_CLEAR, CUP_OUTER_DIA - 2 * WALL)
BASE_INNER_W = max(ORIN_WID + 2 * ORIN_PCB_CLEAR, CUP_OUTER_DIA - 2 * WALL)
BASE_INNER_H = ORIN_LIFT + ORIN_HEIGHT + ORIN_TOP_CLEAR
BASE_OUTER_L = BASE_INNER_L + 2 * WALL
BASE_OUTER_W = BASE_INNER_W + 2 * WALL
BASE_OUTER_H = BASE_INNER_H + WALL  # floor only; open top receives the mic tower
# Foam seat inner (open) diameter — clear window under the mics.
FOAM_SEAT_INNER_DIA = CUP_INNER_DIA - 2 * FOAM_RING_WIDTH
CUP_WALL_H = FOAM_THICKNESS + RESPEAKER_CASE_H * 0.55  # cradle a bit past mid-height


def _base():
    """Vented open-top tub that holds the Orin dev kit."""
    with BuildPart() as base:
        # outer solid, floor at z=0
        Box(BASE_OUTER_L, BASE_OUTER_W, BASE_OUTER_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        # soften vertical outer corners
        vert = base.edges().filter_by(Axis.Z)
        fillet(vert, FILLET)
        # hollow the cavity (open top)
        with Locations(Pos(0, 0, WALL)):
            Box(BASE_INNER_L, BASE_INNER_W, BASE_INNER_H + WALL,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        # standoff pads to lift the board off the floor (underside airflow)
        with Locations(Pos(0, 0, WALL)):
            with GridLocations(ORIN_LEN - 16, ORIN_WID - 16, 2, 2):
                Box(7, 7, ORIN_LIFT,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))

        pitch = VENT_SLOT_W + VENT_GAP

        # --- intake vents: floor slots (cool air drawn up under the board) ---
        with Locations(Pos(0, 0, WALL / 2)):
            with GridLocations(pitch, VENT_SLOT_L + 8, 7, 2):
                Box(VENT_SLOT_W, VENT_SLOT_L, WALL * 3,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT)

        vent_zc = WALL + BASE_INNER_H / 2
        # --- exhaust vents: the -Y long wall (opposite the I/O face) ---
        with Locations(Pos(0, -BASE_OUTER_W / 2, vent_zc)):
            with GridLocations(pitch, 1, 13, 1):
                Box(VENT_SLOT_W, WALL * 3, VENT_SLOT_L,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT)
        # --- exhaust vents: both short end walls (lateral heatsink exhaust) ---
        for x in (BASE_OUTER_L / 2, -BASE_OUTER_L / 2):
            with Locations(Pos(x, 0, vent_zc)):
                with GridLocations(1, pitch, 1, 9):
                    Box(WALL * 3, VENT_SLOT_W, VENT_SLOT_L,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT)

        # --- I/O port windows on the +Y LONG wall (Orin I/O edge) ---
        # Ports run left->right along the board length: DP, 2x USB-A stack,
        # RJ45, USB-C, DC barrel jack. Exact order UNVERIFIED (see README).
        yw = BASE_OUTER_W / 2
        z0 = WALL + ORIN_LIFT + 2  # connector band just above the board plane
        rect_ports = [
            (-42, PORT_DP_W, PORT_DP_H),
            (-22, PORT_USB_W, PORT_USB_H),
            (-4, PORT_USB_W, PORT_USB_H),
            (15, PORT_RJ45_W, PORT_RJ45_H),
            (31, PORT_USBC_W, PORT_USBC_H),
        ]
        for xoff, w, h in rect_ports:
            with Locations(Pos(xoff, yw, z0 + h / 2)):
                Box(w, WALL * 3, h,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT)
        # DC barrel jack — round window
        with Locations(Location((43, yw, z0 + PORT_BARREL_D / 2), (90, 0, 0))):
            Cylinder(PORT_BARREL_D / 2, WALL * 3,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # --- cable pass-through at the top rim (USB up to mic cup) ---
        with Locations(Pos(0, 0, BASE_OUTER_H - 1)):
            Cylinder(CABLE_DIA / 2, WALL * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

    part = base.part
    part.label = "orin_base"
    return part


def _mic_tower():
    """Acoustically-decoupled cup that cradles the stock reSpeaker case."""
    tower_h = DECK + CUP_WALL_H
    with BuildPart() as tower:
        # deck flange that caps the base and carries the cup
        Box(BASE_OUTER_L, BASE_OUTER_W, DECK,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        fillet(tower.edges().filter_by(Axis.Z), FILLET)

        # cup wall rising from the deck
        with Locations(Pos(0, 0, DECK)):
            Cylinder(CUP_OUTER_DIA / 2, CUP_WALL_H,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        # hollow the cup — case cavity above the foam seat
        with Locations(Pos(0, 0, DECK + FOAM_THICKNESS)):
            Cylinder(CUP_INNER_DIA / 2, CUP_WALL_H,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
        # foam gasket seat: a shallow blind recess in the deck top so only the
        # foam ring bears the case. The deck stays SOLID below (isolates Orin
        # fan noise from the mic chamber); vibration path is broken by the foam.
        with Locations(Pos(0, 0, DECK)):
            Cylinder(CUP_INNER_DIA / 2, FOAM_THICKNESS,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)

        # LED ring band — shallow external groove near the top rim (trust ring)
        band_z = tower_h - LED_RING_CHANNEL_W - 2.0
        with Locations(Pos(0, 0, band_z)):
            Cylinder(CUP_OUTER_DIA / 2, LED_RING_CHANNEL_W,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
            Cylinder(CUP_OUTER_DIA / 2 - LED_RING_CHANNEL_D, LED_RING_CHANNEL_W,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.ADD)

        # mute switch hole through the cup wall (privacy feature)
        with Locations(Location((0, CUP_OUTER_DIA / 2, DECK + CUP_WALL_H / 2),
                                (90, 0, 0))):
            Cylinder(MUTE_HOLE_DIA / 2, WALL * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

        # cable channel down through the deck into the base
        with Locations(Pos(0, 0, 0)):
            Cylinder(CABLE_DIA / 2, DECK * 4,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     mode=Mode.SUBTRACT)

    part = tower.part
    part.label = "mic_tower"
    return part


def gen_step():
    base = _base()
    tower = _mic_tower()
    # stack the tower on the base for the assembly preview
    tower.locate(Location((0, 0, BASE_OUTER_H)))
    asm = Compound(label="earbox_v1", children=[base, tower])
    return asm


if __name__ == "__main__":
    shape = gen_step()
    try:
        from build123d import export_step
        export_step(shape, "earbox_v1.step")
        print("wrote earbox_v1.step")
    except Exception as exc:  # pragma: no cover
        print("gen ok, export skipped:", exc)
