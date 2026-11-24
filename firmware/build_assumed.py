"""Build the firmware for the estimated wiring. No device access."""

import os
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from program_aduc814 import load_image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("compiler", nargs="?", default="sdcc")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--measurements", type=Path, help="Build the obstacle guard using the six measured poses")
    mode.add_argument("--half-distance", type=Path, help="Build using measured half-distance poses")
    parser.add_argument("--reference-sensor", type=int, choices=range(1, 5),
                        help="Use this sensor's half-distance trip and release thresholds on all four inputs")
    args = parser.parse_args()
    if args.reference_sensor and not args.half_distance:
        parser.error("--reference-sensor requires --half-distance")
    compiler = shutil.which(args.compiler)
    if not compiler:
        sys.exit("SDCC not found. Pass the path to sdcc.exe.")
    source = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env["PATH"]
    with tempfile.TemporaryDirectory() as work:
        base = [compiler, "-mmcs51", "--model-small", "--code-size", "8192"]
        modules = ["sensor_probe", "motors"] if args.probe else ["aduc814", "receiver", "motors"]
        output = "sensor_probe.ihx" if args.probe else "omni_front1_v3.ihx"
        if args.half_distance:
            from half_distance import thresholds
            records = json.loads(args.half_distance.read_text(encoding="utf-8"))
            if args.reference_sensor:
                reference = args.reference_sensor - 1
                if len(records) <= reference:
                    sys.exit("Missing measurement for the reference sensor.")
                _, _, trip, release = thresholds(reference, records[reference])
                settings = [(channel, True, trip, release) for channel in range(4)]
            else:
                if len(records) != 4:
                    sys.exit("Four sensor measurements are required.")
                settings = [thresholds(i, record) for i, record in enumerate(records)]
        elif args.measurements:
            from calibrate_sensors import fit
            groups = {k: json.loads((args.measurements / (k + ".json")).read_text())
                      for k in ("clear", "1", "2", "3", "4", "clear_end")}
            settings = fit(groups)
        if args.measurements or args.half_distance:
            names = (("char", "channel"), ("char", "rising"), ("int", "trip"), ("int", "release"))
            header = []
            for (kind, name), values in zip(names, zip(*settings)):
                data = ", ".join(str(int(v)) for v in values)
                header.append(f"static const __code unsigned {kind} {name}[] = {{{data}}};")
            (Path(work) / "sensor_config.h").write_text("\n".join(header), encoding="ascii")
            base.extend(["-DOBSTACLE_GUARD", "-I" + work])
            modules.append("obstacle_guard")
            output = "omni_front1_v4_half.ihx" if args.half_distance else "omni_front1_v4.ihx"
            if args.reference_sensor:
                output = f"omni_front1_v4_sensor{args.reference_sensor}.ihx"
        for module in modules:
            subprocess.run(base + ["-c", str(source / (module + ".c"))],
                           cwd=work, env=env, check=True)
        subprocess.run(base + [name + ".rel" for name in modules] + ["-o", output],
                       cwd=work, env=env, check=True)
        artifact = Path(work) / output
        size = len(load_image(artifact))
        shutil.copyfile(artifact, source / output)
        print(f"{output}: {size} bytes")


if __name__ == "__main__":
    main()
