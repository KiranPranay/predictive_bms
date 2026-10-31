#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-/dev/ttyUSB0}"

echo "========================================================"
echo "Predictive BMS: Flashing ESP32 Firmware on $PORT"
echo "========================================================"

if [ ! -e "$PORT" ]; then
    echo "ERROR: Device $PORT not found!"
    echo "Available serial ports:"
    ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No serial devices detected."
    exit 1
fi

if [ ! -r "$PORT" ] || [ ! -w "$PORT" ]; then
    echo "ERROR: Permission denied on $PORT"
    echo "Please grant permission with:"
    echo "    sudo chmod 666 $PORT"
    echo "or add user to dialout group:"
    echo "    sudo usermod -aG dialout \$USER"
    exit 1
fi

export IDF_TOOLS_PATH="$DIR/.tools/espressif"
source "$DIR/.tools/esp-idf/export.sh"

cd "$DIR/firmware"
echo "Flashing firmware to $PORT..."
idf.py -p "$PORT" flash

echo ""
echo "========================================================"
echo "SUCCESS: Firmware flashed successfully to ESP32!"
echo "ESP32 Wi-Fi Access Point: PredictiveBMS"
echo "Password:                 bms-prototype"
echo "Web Dashboard URL:        http://192.168.4.1/"
echo "========================================================"

