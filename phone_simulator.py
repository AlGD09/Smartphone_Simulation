#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import signal
import sys
from ble.advertising import start_advertising, stop_advertising
from ble.gatt_services import start_gatt_server

# Globale Referenz auf die GLib-Schleife
gatt_loop = None

def run_gatt():
    """Startet den GATT-Server in einem eigenen Thread."""
    global gatt_loop
    gatt_loop = start_gatt_server()
    if gatt_loop:
        gatt_loop.run()

def cleanup_and_exit():
    """Beendet alle Prozesse sauber."""
    print("\n🧹 Stoppe Bluetooth-Simulation...")
    stop_advertising()
    if gatt_loop:
        try:
            gatt_loop.quit()
        except Exception:
            pass
    print("✅ Alles gestoppt.")
    sys.exit(0)

if __name__ == "__main__":
    print("📱 Starte Smartphone-Simulation (Advertising + GATT)...")

    # Beende sauber bei STRG + C
    signal.signal(signal.SIGINT, lambda sig, frame: cleanup_and_exit())

    # GATT-Server in separatem Thread starten
    gatt_thread = threading.Thread(target=run_gatt, daemon=True)
    gatt_thread.start()

    # Advertising starten
    start_advertising()

    # Haupt-Thread wartet einfach
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_and_exit()
