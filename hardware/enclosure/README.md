# earbox — founder-unit enclosure v1 ("le boitier")

Two-chamber tower housing the **NVIDIA Jetson Orin Nano Super Developer Kit**
(lower, vented chamber) and the **Seeed reSpeaker XVF3800 USB 4-mic array**
(upper chamber, kept in its **stock retail case** for v1). Generated with
[text-to-cad](https://github.com/earthtojake/text-to-cad) / build123d.

> **v1 scope:** keep the reSpeaker in its factory case (mic geometry preserved,
> simplest path). A bare-board v2 that reproduces the 66 mm mic square can come
> later. Every model dimension is a named variable at the top of
> `earbox_v1.py`; the acoustically-critical ones are one-line adjustable.

## Files

| File | What |
| --- | --- |
| `earbox_v1.py` | Parametric build123d source. `gen_step()` returns the 2-part assembly (`orin_base` + `mic_tower`). |
| `earbox_v1.step` | Primary CAD artifact (assembly). |
| `earbox_v1.stl` | Printable mesh sidecar. |
| `foam_gasket.py` | 2D generator for the laser-cut foam decoupling ring. |
| `foam_gasket.dxf` | Laser-cut layout for Laurent (foam). |
| `preview.png` | Isometric preview render. |

Regenerate after editing dims:

```bash
# from tools/text-to-cad with its venv active, run against this dir
python skills/cad/scripts/step /Users/tony/work/earbox/hardware/enclosure/earbox_v1.py \
  --stl /Users/tony/work/earbox/hardware/enclosure/earbox_v1.stl
# or standalone: python earbox_v1.py  (writes earbox_v1.step)
python foam_gasket.py
```

## Architecture

```
            ___________________            <- reSpeaker mics face up, ~6 mm proud
           /   reSpeaker case  \           <- STOCK retail case (kept intact)
          | [ ]  mic  puck  [ ] |          <- LED ring band recessed near rim
          |=== foam gasket ring ===|       <- ONLY load path (laser-cut foam)
       ___|_______ deck __________|___     <- SOLID deck: isolates fan noise
      |    |  cable channel (USB)  |   |    <- one 9 mm pass-through, deck solid elsewhere
      |    +-------------------+    |  <-- mute switch hole (privacy) on cup wall
      |     Jetson Orin Nano Super   |
      |  [====== fan / heatsink ===] |     <- exhaust vents on 3 side walls (high)
      | O O   standoffs lift board   |     <- intake vents in the floor
      |__[I/O ports: DP USB USB RJ45 USB-C DC]__|  <- +Y long wall
```

- **Two chambers, acoustically decoupled.** The cased reSpeaker rests only on a
  laser-cut **foam gasket ring** seated in a recess in the cup floor; there is
  radial clearance (`RESPEAKER_RADIAL_CLEAR`, 1 mm) between the case and the cup
  wall, so there is **no rigid path** from the mic case to the chassis. The deck
  under the gasket is **solid** (except the cable channel), so the Orin fan's
  airborne noise is blocked from the mic chamber and the foam breaks the
  vibration path.
- **Real airflow for the Orin.** Intake slots in the floor (cool air drawn up
  under the lifted board), exhaust slots high on three side walls. `ORIN_LIFT`
  (4 mm) standoffs create an underside plenum. Nothing sits directly over the
  fan; `ORIN_TOP_CLEAR` (8 mm) leaves head-room above the fan to the deck.
- **Cable channel.** A single 9 mm channel through the deck routes the USB-C
  from the reSpeaker down to a USB-A port on the Orin.
- **I/O openings** on the +Y long wall: DisplayPort, 2× USB-A (double stack),
  RJ45, USB-C, DC barrel jack. The board registers against this wall so
  connectors align with the windows.
- **Privacy mute switch** hole on the cup wall (7 mm, panel-mount).
- **LED ring band**: shallow external recess near the cup's top rim where
  Fabien's trust-interface LED ring can later seat (depth < wall, non-breaching).

## Dimensions — VERIFIED vs UNVERIFIED

Per Laurent/Iris: online reSpeaker case dims diverge, so **every reSpeaker case
value below is UNVERIFIED and must be caliper-checked (or measured from Seeed's
official STEP) before printing.** VERIFIED = official datasheet/spec.

### Jetson Orin Nano Super Dev Kit (P3768 reference carrier)

| Dim | Value | Status | Source |
| --- | --- | --- | --- |
| Board L × W | 100 × 79 mm | **VERIFIED** | NVIDIA Orin Nano Dev Kit datasheet |
| Assembled height (incl. thermal) | **30 mm used** (datasheet says 21 mm "incl. feet, carrier, module, thermal"; jetsonhacks quotes 30 mm) | **UNVERIFIED / conflict** | NVIDIA datasheet vs jetsonhacks — we default to the larger 30 mm so the fan is never choked. Caliper the real Super fan; if ~21 mm set `ORIN_HEIGHT=21`. |
| DC barrel jack | 5.5 mm OD / 2.5 mm ID, centre-positive | **VERIFIED** | NVIDIA hardware_layout |
| USB-C (data) | 1× | **VERIFIED** | NVIDIA hardware_layout |
| I/O all on one long edge | DP → 2× USB-A stack (4 ports) → RJ45 → USB-C → DC jack | edge **VERIFIED** (photos); exact left→right order **UNVERIFIED** | NVIDIA hardware_layout + product photos |
| 40-pin GPIO header | opposite long edge | **UNVERIFIED** (standard P3768) | — |
| microSD | on the module underside | **VERIFIED** | NVIDIA callout |
| Mounting-hole pattern | not published | **UNVERIFIED** | pull from NVIDIA STEP or measure |
| Fan airflow | top axial fan, blows **down** through fins, exhausts laterally | type **VERIFIED**, vector **UNVERIFIED** | assembly type |

### Seeed reSpeaker XVF3800 (retail, in stock case)

| Dim | Value | Status | Source |
| --- | --- | --- | --- |
| PCB shape | circular | **VERIFIED** | Seeed wiki / product page |
| Bare PCB diameter | ~99 mm (× 4 mm thick) | **UNVERIFIED** | cnx-software (third-party) — note: brief said ~70 mm, actual is ~99 mm |
| Stock case outer diameter | **102 mm used** | **UNVERIFIED** | no official case dim exists; measure Seeed p-6490 STEP or caliper |
| Stock case height | **20 mm used** | **UNVERIFIED** | measure Seeed p-6490 STEP or caliper |
| Case shape | round | **VERIFIED** (shape only) | Seeed p-6490 page |
| Mic array geometry | 4 mics on a 66 mm square (diag ~93.3 mm, radius ~46.7 mm) | **VERIFIED** | Seeed wiki mic coordinates |
| USB | USB-C (UAC 2.0); 2nd USB-C for firmware | **VERIFIED** | Seeed wiki |
| Case SKU | with-case = p-6490 (base p-6488 is bare board) | **VERIFIED** | Seeed product pages |
| Mounting holes | not published | **UNVERIFIED** | measure STEP |

## Derived enclosure envelope (at current defaults)

| Quantity | Value |
| --- | --- |
| Base outer (L × W × H) | 111 × 110 × 45 mm |
| Mic tower (dia × H) | 110 mm × 17 mm |
| Overall height (base + tower + case proud) | ~68 mm |
| Wall / deck thickness | 3.0 mm |
| Cup inner dia (case + 2×clearance) | 104 mm |
| Foam gasket ring | OD 104 / ID 92 mm |

> The cased mic puck (~110 mm) is wider than the bare Orin footprint (~90 mm),
> so the base is grown to fully support the puck; the extra interior around the
> board is air plenum (helps, does not choke, the fan).

## Print notes

- FDM, 3 mm walls, no heroic supports intended. Print the **two parts
  separately**, each open-side-down:
  - `orin_base`: print floor-down; port windows and side vents print as wall
    openings (bridged), no supports needed.
  - `mic_tower`: print deck-down (cup opening up); the cup is a simple upward
    cavity — no supports. The LED band and mute hole are shallow/side features.
- Suggested: 0.2 mm layers, 3–4 perimeters, 20–30% infill (PETG or ASA for
  heat near the Jetson; PLA fine for a bench mock-up).
- Cable channel and mute hole may need a light chamfer/ream after printing.
- The two parts are a clearance stack in v1 (tower sits on the base rim). Add
  screw bosses / a lip catch in v2 once real parts are calipered.

## Foam gasket spec (for Laurent)

- **Part:** flat annular ring, laser-cut from foam.
- **OD:** 104 mm (= cup inner diameter; `CUP_INNER_DIA`).
- **ID:** 92 mm (open window under the mics; `FOAM_SEAT_INNER_DIA`).
- **Thickness:** **3 mm assumed — please confirm** (`FOAM_THICKNESS`). This sets
  both the gasket-seat recess depth and the mic stand-off, so the CAD updates
  with whatever foam stock you pick.
- **Material:** soft closed-cell (EVA / PORON / EPDM) for damping; final
  durometer your call.
- Layout: `foam_gasket.dxf`.

## Open questions for Laurent

1. **Foam thickness / material** for the gasket (drives seat depth + standoff).
2. **Real Orin Super stack height** incl. fan — 21 mm (datasheet) or ~30 mm
   (measured)? Sets `ORIN_HEIGHT` and the whole lower-chamber height.
3. **reSpeaker stock case** real OD + height (caliper) — sets the cup.
4. **PSU strategy:** barrel-jack brick external, or integrate a DC supply inside
   the base? v1 assumes external brick, barrel jack only.
5. Mounting: screw bosses vs clip lip between base and tower for v2.
