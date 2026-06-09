#!/usr/bin/env python3
"""Probe each TTP223 line independently. Touch one pad at a time; you should see
the corresponding line print HIGH then LOW. Ctrl+C to exit.

Wiring (OrangePi 4 Pro, A733 / sun60iw2):
  S1 -> header pin 29 / PD0 / gpiochip0 line 96   (left-most pad)
  S2 -> header pin 31 / PD1 / gpiochip0 line 97
  S3 -> header pin 33 / PD2 / gpiochip0 line 98
  S4 -> header pin 35 / PD3 / gpiochip0 line 99   (right-most pad)
  VCC -> 3.3V (header pin 17)  [NOT 5V]
  GND -> GND   (header pin 25 or 39)

Requires libgpiod >= 2.0 (PyPI `gpiod>=2.0`). The user running this needs to be
in the `gpio` group so /dev/gpiochip0 is openable without sudo.
"""
import time
import gpiod
from gpiod.line import Bias, Direction, Value

CHIP = "/dev/gpiochip0"
LINES = [96, 97, 98, 99]
NAMES = {96: "S1", 97: "S2", 98: "S3", 99: "S4"}

settings = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_DOWN)
config = {l: settings for l in LINES}

with gpiod.request_lines(CHIP, consumer="ttp223-probe", config=config) as req:
    print("Probing", LINES, "(PULL_DOWN). Touch each pad. Ctrl+C to exit.")
    last = {l: None for l in LINES}
    while True:
        vals = req.get_values(LINES)
        for line, v in zip(LINES, vals):
            high = (v == Value.ACTIVE)
            if last[line] != high:
                print(f"{time.strftime('%H:%M:%S')}  {NAMES[line]} (line {line}) = {'HIGH' if high else 'LOW'}")
                last[line] = high
        time.sleep(0.02)
