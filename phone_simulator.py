#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ble.advertising import start_advertising, stop_advertising
from ble.gatt_services import start_gatt_server
from cloud.cloud_request import CloudClient
import threading, time, signal, sys

gatt_thread = None

def run_gatt(token_bytes):
    start_gatt_server(token_bytes)   # <— WICHTIG: Token weitergeben!

def cleanup_and_exit(sig=None, frame=None):
    print("\n Stoppe Bluetooth-Simulation...")
    stop_advertising()
    print(" Alles gestoppt.")
    sys.exit(0)

if __name__ == "__main__":
    print("Starte Smartphone-Simulation ...")

    device_id = "bd45e75870af93c2"
    secret_hash = "cc03e747a6afbbcbf8be7668acfebee5"

    cloud = CloudClient()
    token_str = cloud.request_token(device_id, secret_hash)   # akzeptiert "token" oder "auth_token"
    if not token_str:
        print("❌ Kein Token erhalten – Abbruch.")
        sys.exit(1)

    print(f"✅ Token erhalten: {token_str}")
    token_bytes = bytes.fromhex(token_str) if all(c in "0123456789abcdef" for c in token_str.lower()) else token_str.encode()

    signal.signal(signal.SIGINT, cleanup_and_exit)

    gatt_thread = threading.Thread(target=run_gatt, args=(token_bytes,), daemon=True)
    gatt_thread.start()

    start_advertising()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_and_exit()
