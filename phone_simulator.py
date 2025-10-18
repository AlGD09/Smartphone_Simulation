#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import signal
import sys
from ble.advertising import start_advertising, stop_advertising
from ble.gatt_services import start_gatt_server

gatt_thread = None

def run_gatt():
    start_gatt_server()

def cleanup_and_exit(sig=None, frame=None):
    print("\n🧹 Stoppe Bluetooth-Simulation...")
    stop_advertising()
    print("✅ Alles gestoppt.")
    sys.exit(0)

if __name__ == "__main__":
    print("📱 Starte Smartphone-Simulation (Advertising + GATT)...")

    signal.signal(signal.SIGINT, cleanup_and_exit)

    gatt_thread = threading.Thread(target=run_gatt, daemon=True)
    gatt_thread.start()

    start_advertising()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_and_exit()
