#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ble.advertising import start_advertising, stop_advertising
import time

if __name__ == "__main__":
    print("📱 Starte Smartphone-Simulation (Advertising + später GATT)...")

    try:
        start_advertising()
    except KeyboardInterrupt:
        stop_advertising()
        print("Programm beendet.")
