#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus, dbus.mainloop.glib, dbus.service
from gi.repository import GLib
import hmac, hashlib
import time

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

SERVICE_UUID   = "0000aaa0-0000-1000-8000-aabbccddeeff"
CHAR_CHALLENGE = "0000aaa2-0000-1000-8000-aabbccddeeff"
CHAR_RESPONSE  = "0000aaa1-0000-1000-8001-aabbccddeeff"

ADAPTER_PATH   = "/org/bluez/hci0"
SERVICE_PATH   = "/org/bluez/example/service0"
CHALLENGE_PATH = SERVICE_PATH + "/char_challenge"
RESPONSE_PATH  = SERVICE_PATH + "/char_response"

EXPECTED_TOKEN = b"\xDE\xAD\xBE\xEF"  # nur Platzhalter bis erste Challenge verarbeitet ist

RCU_IDS = {}

def calc_hmac_response(challenge: bytes, key: bytes) -> bytes:
    return hmac.new(key, challenge, hashlib.sha256).digest()

class Characteristic(dbus.service.Object):
    def __init__(self, bus, uuid, flags, path, service_path):
        self.path = path
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.service_path = service_path
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == "org.bluez.GattCharacteristic1":
            return {
                "UUID": self.uuid,
                "Service": dbus.ObjectPath(self.service_path),
                "Flags": dbus.Array(self.flags, signature="s"),
            }
        return {}

class ChallengeCharacteristic(Characteristic):
    def __init__(self, bus, path, service_path, response_char, hmac_key: bytes):
        super().__init__(bus, CHAR_CHALLENGE, ["write"], path, service_path)
        self.response_char = response_char
        self.hmac_key = hmac_key or b""
        self._buffer = bytearray()

    @dbus.service.method("org.bluez.GattCharacteristic1",
                         in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        try:
            offset = int(options.get("offset", 0))
        except Exception:
            offset = 0

        chunk = bytes(value)
        if offset == 0:
            self._buffer = bytearray(chunk)
        else:
            if offset > len(self._buffer):
                self._buffer.extend(b"\x00" * (offset - len(self._buffer)))
            self._buffer[offset:offset+len(chunk)] = chunk

        if len(self._buffer) >= 23:
            challenge = bytes(self._buffer[:16])
            rcu_id = bytes(self._buffer[16:23])
            print(f"Challenge empfangen: {challenge.hex()}")
            print(f"RCU-ID vom Challenge: {rcu_id.decode("utf-8")}")

            timestamp = time.time()
            rcuId = rcu_id.decode("utf-8")
            if rcuId not in RCU_IDS: 
                RCU_IDS[rcuId] = timestamp

            if not self.hmac_key:
                print(" Kein HMAC-Key gesetzt – Fallback-Token als Antwort.")
                response = EXPECTED_TOKEN
            else:
                response = calc_hmac_response(challenge, self.hmac_key)

            self.response_char.set_response(response)
            print(f"→ Berechneter Response gesetzt: {response.hex()}")
            self._buffer.clear()

class ResponseCharacteristic(Characteristic):
    def __init__(self, bus, path, service_path, initial_token=None):
        super().__init__(bus, CHAR_RESPONSE, ["read"], path, service_path)
        self.response = EXPECTED_TOKEN if initial_token is None else initial_token

    def set_response(self, resp: bytes):
        self.response = resp if resp and isinstance(resp, (bytes, bytearray)) else EXPECTED_TOKEN

    @dbus.service.method("org.bluez.GattCharacteristic1",
                         in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        try:
            value = bytes(self.response) if self.response else EXPECTED_TOKEN

            # Optional: MTU beachten, falls mitgeliefert (BlueZ übergibt 'mtu' nicht in allen Versionen)
            mtu = options.get("mtu")
            if mtu is not None:
                try:
                    mtu = int(mtu)
                    if mtu > 0:
                        # ATT-Read: häufig (MTU - 1) nutzbar; defensiv hart limitieren
                        max_len = max(1, mtu - 1)
                        value = value[:max_len]
                except Exception:
                    pass

            # Offset sauber bedienen
            try:
                offset = int(options.get("offset", 0))
            except Exception:
                offset = 0
            if offset < 0 or offset > len(value):
                chunk = b""
            else:
                chunk = value[offset:]

            print(f"Response abgefragt (HEX, offset={offset}): {chunk.hex() if chunk else '<leer>'}")

            # **Wichtig**: ByteArray ist am robustesten
            return dbus.ByteArray(chunk)

        except Exception as e:
            print(f"Fehler in ReadValue(): {e}")
            return dbus.ByteArray(b"\x00")

class AuthService(dbus.service.Object):
    def __init__(self, bus, path, token: bytes):
        self.path = path
        self.bus = bus
        dbus.service.Object.__init__(self, bus, path)

        self.response_char  = ResponseCharacteristic(bus, RESPONSE_PATH, self.path)
        self.challenge_char = ChallengeCharacteristic(bus, CHALLENGE_PATH, self.path, self.response_char, token)

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == "org.bluez.GattService1":
            return {"UUID": SERVICE_UUID, "Primary": True}
        return {}

    @dbus.service.method("org.bluez.GattService1",
                         in_signature="", out_signature="ao")
    def GetCharacteristics(self):
        return [dbus.ObjectPath(CHALLENGE_PATH), dbus.ObjectPath(RESPONSE_PATH)]

class Application(dbus.service.Object):
    def __init__(self, bus, token: bytes):
        self.path = "/"
        self.bus = bus
        dbus.service.Object.__init__(self, bus, self.path)
        self.service = AuthService(bus, SERVICE_PATH, token)

    @dbus.service.method("org.freedesktop.DBus.ObjectManager",
                         in_signature="", out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        return {
            self.service.path: {
                "org.bluez.GattService1": {"UUID": SERVICE_UUID, "Primary": True},
            },
            CHALLENGE_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": CHAR_CHALLENGE,
                    "Service": dbus.ObjectPath(SERVICE_PATH),
                    "Flags": ["write"],
                },
            },
            RESPONSE_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": CHAR_RESPONSE,
                    "Service": dbus.ObjectPath(SERVICE_PATH),
                    "Flags": ["read"],
                },
            },
        }

def start_gatt_server(token: bytes):
    bus = dbus.SystemBus()
    adapter = bus.get_object("org.bluez", ADAPTER_PATH)
    gatt_manager = dbus.Interface(adapter, "org.bluez.GattManager1")

    app = Application(bus, token)

    print("Registriere GATT-Service...")
    gatt_manager.RegisterApplication(
        app.path,
        {},
        reply_handler=lambda: print(f"GATT-Service aktiv – UUID: {SERVICE_UUID}"),
        error_handler=lambda e: print("Fehler bei RegisterApplication:", e),
    )

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n GATT-Server beendet.")

if __name__ == "__main__":
    print("Bitte über phone_simulator.py starten (Token aus Cloud abrufen).")
