"""Build driver: STEP + STL for the enclosure, DXF for the foam gasket.

Uses build123d directly (the text-to-cad engine) so it runs without the
cadpy skill runtime (cadpy needs py>=3.12; this box is on 3.11).
"""

from build123d import export_step, export_stl

import earbox_v1
import foam_gasket


def main():
    shape = earbox_v1.gen_step()
    export_step(shape, "earbox_v1.step")
    print("wrote earbox_v1.step")
    export_stl(shape, "earbox_v1.stl")
    print("wrote earbox_v1.stl")

    sk = foam_gasket.gen_dxf()
    foam_gasket.write_dxf(sk, "foam_gasket.dxf")
    print("wrote foam_gasket.dxf")


if __name__ == "__main__":
    main()
