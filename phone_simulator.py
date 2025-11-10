#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os 
import json
from ble.advertising import start_advertising, stop_advertising
from ble.gatt_services import start_gatt_server
from cloud.cloud_request import CloudClient
import threading, time, signal, sys

gatt_thread = None

def run_gatt(token_bytes):
    start_gatt_server(token_bytes)   

def cleanup_and_exit(sig=None, frame=None):
    print("\n Stoppe Bluetooth-Simulation...")
    stop_advertising()
    print(" Alles gestoppt.")
    sys.exit(0)


def load_or_request_credentials(): 
    # Datei in selber Repo speichern
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_file = os.path.join(script_dir, "user_data.json")

    # Prüfen, ob Datei existiert
    if os.path.exists(creds_file):
        try:
            with open(creds_file, "r", encoding="utf-8") as f:
                creds = json.load(f)
            if creds.get("username") and creds.get("secret_hash"):
                print("Zugangsdaten geladen.")
                return creds["username"], creds["secret_hash"]
        except (OSError, json.JSONDecodeError):
            print("Fehler beim Laden gespeicherter Zugangsdaten, Eingabe erforderlich.")

    # Wenn nichts vorhanden: Eingabe anfordern
    print("Bitte Zugangsdaten eingeben:")
    username = input("Benutzername: ").strip()
    secret_hash = input("Secret Hash (oder Passwort-Hash): ").strip()

    # Speichern
    creds = {"username": username, "secret_hash": secret_hash}
    with open(creds_file, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)
    print(f"Zugangsdaten gespeichert unter: {creds_file}")

    return username, secret_hash

if __name__ == "__main__":
    print("Starte Smartphone-Simulation ...")

    username, secret_hash = load_or_request_credentials()
    #username = "Admin"
    device_id = "bd45e75870af93c2"
    #secret_hash = "cc03e747a6afbbcbf8be7668acfebee5"

    cloud = CloudClient()
    token_str = cloud.request_token(username, device_id, secret_hash)   # akzeptiert "token" oder "auth_token"
    if not token_str:
        print("Kein Token erhalten – Abbruch.")
        sys.exit(1)

    print(f"Token erhalten: {token_str}")
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
