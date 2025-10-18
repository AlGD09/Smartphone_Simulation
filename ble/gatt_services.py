#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
import hmac, hashlib

# --- BlueZ / D-Bus Setup ------------------------------------------------------
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

# --- UUIDs / Paths -------------------------------------------------------------
SERVICE_UUID   = "0000aaa0-0000-1000-8000-aabbccddeeff"
CHAR_CHALLENGE = "0000aaa2-0000-1000-8000-aabbccddeeff"
CHAR_RESPONSE  = "0000aaa1-0000-1000-8001-aabbccddeeff"

ADAPTER_PATH   = "/org/bluez/hci0"
SERVICE_PATH   = "/org/bluez/example/service0"
CHALLENGE_PATH = SERVICE_PATH + "/char_challenge"
RESPONSE_PATH  = SERVICE_PATH + "/char_response"

# --- Auth Setup ----------------------------------------------------------------
SHARED_KEY     = b"this_is_test_key_32bytes5555"  # muss zur RCU passen
EXPECTED_TOKEN = b"\xDE\xAD\xBE\xEF"             # Fallback (RCU akzeptiert .endswith)

def calc_hmac_response(challenge: bytes) -> bytes:
    return hmac.new(SHARED_KEY, challenge, hashlib.sha256).digest()

# --- Basis-Klassen -------------------------------------------------------------
class Characteristic(dbus.service.Object):
    """Basis-GATT-Characteristic-Klasse (BlueZ GATT over D-Bus)."""

    def __init__(self, bus, uuid, flags, path, service_path):
        self.path = path
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        # service_path MUSS als dbus.ObjectPath veröffentlicht werden
        self.service_path = service_path
        dbus.service.Object.__init__(self, bus, path)

    # Properties API
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

    # Optional (nicht zwingend): einzelne Get/Set-Methoden könnten hier ergänzt werden.


# --- Challenge (WRITE) ---------------------------------------------------------
class ChallengeCharacteristic(Characteristic):
    """Characteristic, die die Challenge vom Central (RCU) empfängt."""

    def __init__(self, bus, path, service_path, response_char):
        super().__init__(bus, CHAR_CHALLENGE, ["write"], path, service_path)
        self.response_char = response_char
        self._buffer = bytearray()  # falls BlueZ in mehreren Blöcken mit 'offset' schreibt

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
            # defensiv: bei Offset > 0 korrekt einfügen/anhängen
            if offset > len(self._buffer):
                # fülle ggf. Lücke (sollte BlueZ i.d.R. nicht tun, aber sicher ist sicher)
                self._buffer.extend(b"\x00" * (offset - len(self._buffer)))
            # überschreiben/anhängen
            self._buffer[offset:offset+len(chunk)] = chunk

        # Falls das komplette Paket in einem Schlag kam (typisch), direkt verarbeiten:
        # Da wir das genaue Protokoll (Länge) kennen: Challenge = 16 byte
        if len(self._buffer) >= 16:
            challenge = bytes(self._buffer[:16])
            print(f"Challenge empfangen: {challenge.hex()}")

            # Echten HMAC-Response berechnen:
            response = calc_hmac_response(challenge)
            self.response_char.set_response(response)
            print(f"→ Berechneter Response gesetzt: {response.hex()}")

            # Zusätzlich (für Fallback-Tests) könnte man ans Ende DEADBEEF anhängen:
            # self.response_char.set_response(response + EXPECTED_TOKEN)

            # Buffer leeren, um nächste Challenge sauber zu empfangen
            self._buffer.clear()


# --- Response (READ) -----------------------------------------------------------
class ResponseCharacteristic(Characteristic):
    """Characteristic, von der die RCU den Response liest."""

    def __init__(self, bus, path, service_path):
        super().__init__(bus, CHAR_RESPONSE, ["read"], path, service_path)
        # Initialer Wert (Fallback – wird durch Challenge überschrieben)
        self.response = EXPECTED_TOKEN

    def set_response(self, resp: bytes):
        # defensiv: nie None/leer lassen
        self.response = resp if resp and isinstance(resp, (bytes, bytearray)) else EXPECTED_TOKEN

    @dbus.service.method("org.bluez.GattCharacteristic1",
                         in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        try:
            value = bytes(self.response) if self.response else EXPECTED_TOKEN
            try:
                offset = int(options.get("offset", 0))
            except Exception:
                offset = 0

            # Offsets korrekt bedienen (BlueZ kann in Blöcken lesen)
            if offset < 0 or offset > len(value):
                # ungültiger Offset -> leere Antwort (oder 0x00)
                print(f"ReadValue: ungültiger Offset {offset}, Länge {len(value)}")
                chunk = b""
            else:
                chunk = value[offset:]

            print(f"Response abgefragt (HEX, offset={offset}): {chunk.hex() if chunk else '<leer>'}")

            # Korrekte D-Bus Antwort: ay  (Array of bytes)
            return dbus.Array([dbus.Byte(b) for b in chunk], signature="y")

        except Exception as e:
            print(f"Fehler in ReadValue(): {e}")
            # stets gültigen Rückgabewert liefern, um 0x0e zu vermeiden
            return dbus.Array([dbus.Byte(0x00)], signature="y")


# --- Service & Application -----------------------------------------------------
class AuthService(dbus.service.Object):
    """GATT-Service mit Challenge- und Response-Characteristics."""

    def __init__(self, bus, path):
        self.path = path
        self.bus = bus
        dbus.service.Object.__init__(self, bus, path)

        # Reihenfolge wichtig: Response-Char zuerst anlegen, damit Challenge-Char sie referenzieren kann
        self.response_char  = ResponseCharacteristic(bus, RESPONSE_PATH, self.path)
        self.challenge_char = ChallengeCharacteristic(bus, CHALLENGE_PATH, self.path, self.response_char)

    # Service-Properties
    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == "org.bluez.GattService1":
            return {"UUID": SERVICE_UUID, "Primary": True}
        return {}

    # optional, BlueZ nutzt meist ObjectManager unten
    @dbus.service.method("org.bluez.GattService1",
                         in_signature="", out_signature="ao")
    def GetCharacteristics(self):
        return [dbus.ObjectPath(CHALLENGE_PATH), dbus.ObjectPath(RESPONSE_PATH)]


class Application(dbus.service.Object):
    """Implementiert ObjectManager für BlueZ GATT."""

    def __init__(self, bus):
        self.path = "/"
        self.bus = bus
        dbus.service.Object.__init__(self, bus, self.path)
        self.service = AuthService(bus, SERVICE_PATH)

    @dbus.service.method("org.freedesktop.DBus.ObjectManager",
                         in_signature="", out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        # Vollständiges, konsistentes Objektmodell bereitstellen
        return {
            self.service.path: {
                "org.bluez.GattService1": {
                    "UUID": SERVICE_UUID,
                    "Primary": True,
                },
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


# --- Start ---------------------------------------------------------------------
def start_gatt_server():
    bus = dbus.SystemBus()
    adapter = bus.get_object("org.bluez", ADAPTER_PATH)
    gatt_manager = dbus.Interface(adapter, "org.bluez.GattManager1")

    app = Application(bus)

    print("Registriere GATT-Service...")
    gatt_manager.RegisterApplication(
        app.path,
        {},
        reply_handler=lambda: print(f"✅ GATT-Service aktiv – UUID: {SERVICE_UUID}"),
        error_handler=lambda e: print("❌ Fehler bei RegisterApplication:", e),
    )

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n🛑 GATT-Server beendet.")


if __name__ == "__main__":
    start_gatt_server()
