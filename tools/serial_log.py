#!/usr/bin/env python3
"""Records the firmware's CSV telemetry from the serial port to a file.

Sends "log 1" (or "log 5"), writes every line that starts with "CSV," to the file without the
prefix, and shows every other line on the screen. Ctrl-C stops the log ("log off") and closes
the file. Use the file with tools/fit_thermal.py (Gate 9).

    python3 tools/serial_log.py /dev/ttyUSB0 gate9.csv [--rate 1]     (Windows: COM3)

Needs pyserial (tools/requirements.txt).
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is missing: .venv/bin/pip install -r tools/requirements.txt")


def main(argv=None):
    ap = argparse.ArgumentParser(description="capture CSV telemetry from the ESP32")
    ap.add_argument("port")
    ap.add_argument("out")
    ap.add_argument("--rate", choices=("1", "5"), default="1", help="lines per second")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args(argv)

    rows = 0
    with serial.Serial(args.port, args.baud, timeout=1) as port, \
            open(args.out, "w", newline="") as out:
        port.write(f"log {args.rate}\r\n".encode())
        header_seen = False
        print(f"Logging to {args.out}; Ctrl-C to stop.")
        try:
            while True:
                line = port.readline().decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    continue
                if line.startswith("CSV,"):
                    body = line[4:]
                    if body.startswith("t_s,"):
                        if header_seen:
                            continue   # the header comes again if the log is restarted
                        header_seen = True
                    out.write(body + "\n")
                    rows += 1
                    if rows % 60 == 0:
                        out.flush()
                        print(f"  {rows} lines", end="\r")
                else:
                    print(line)
        except KeyboardInterrupt:
            pass
        finally:
            port.write(b"log off\r\n")
            time.sleep(0.2)
    print(f"\n{rows} lines written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
