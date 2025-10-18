#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gatt_services.py – BLE GATT Server für Smartphone-Simulation
"""

import dbus
import dbus.mainloop.glib
import dbus.service
import hmac
import hashlib
from gi.repository import GLib

SERVICE_UUID = "0000aaa0-0000-1000-8000-aabbccddeeff"
CHAR_CHALLENGE = "0000aaa2-0000-1000-8000-aabbccddeeff"
CHAR_RESPONSE = "0000aaa1-0000-1000-8001-aabbccddeeff"

SHARED_KEY = b"this_is_test_key_32bytes____"

ADAPTER_PATH = "/org/bluez/hci1"
SERVICE_PATH = "/org/bluez/example/service0"
CHALLENGE_PATH = SERVICE_PATH + "/char_challenge"
RESPONSE_PATH = SERVICE_PATH + "/char_response"


def generate_response(challenge: bytes) -> bytes:
    """Berechnet die HMAC-Response aus der empfangenen Challenge."""
    return hmac.new(SHARED_KEY, challenge, hashlib.sha256).digest()


class Characteristic(dbus.service.Object):
    """Basis-GATT-Characteristic-Klasse."""

    def __init__(self, bus, uuid, flags, path, service):
        self.path = path
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.service = service
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == "org.bluez.GattCharacteristic1":
            return {
                "UUID": self.uuid,
                "Service": self.service,
                "Flags": self.flags,
            }
        return {}

    def ReadValue(self, options):
        return []

    def WriteValue(self, value, options):
        pass


class ChallengeCharacteristic(Characteristic):
    """Characteristic, die die Challenge vom Central (RCU) empfängt."""

    def __init__(self, bus, path, service):
        super().__init__(bus, CHAR_CHALLENGE, ["write"], path, service)
        self.last_challenge = None

    @dbus.service.method("org.bluez.GattCharacteristic1",
                         in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        self.last_challenge = bytes(value)
        print(f"Challenge empfangen: {self.last_challenge.hex()}")
        self.service.handle_challenge(self.last_challenge)


class ResponseCharacteristic(Characteristic):
    """Characteristic, von der die RCU den berechneten Response liest."""

    def __init__(self, bus, path, service):
        super().__init__(bus, CHAR_RESPONSE, ["read"], path, service)
        self.response = b""

    @dbus.service.method("org.bluez.GattCharacteristic1",
                         in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        print(f"Response abgefragt: {self.response.hex()}")
        return [dbus.Byte(b) for b in self.response]


class AuthService(dbus.service.Object):
    """Custom Authentifizierungs-Service."""

    def __init__(self, bus, path):
        self.path = path
        self.bus = bus
        dbus.service.Object.__init__(self, bus, path)

        self.challenge_char = ChallengeCharacteristic(bus, CHALLENGE_PATH, self.path)
        self.response_char = ResponseCharacteristic(bus, RESPONSE_PATH, self.path)

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == "org.bluez.GattService1":
            return {
                "UUID": SERVICE_UUID,
                "Primary": True,
            }
        return {}

    def handle_challenge(self, challenge: bytes):
        """Berechnet die Response und speichert sie in der ResponseCharacteristic."""
        response = generate_response(challenge)
        print(f"Response berechnet: {response.hex()}")
        self.response_char.response = response


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
        managed_objects = {
            self.service.path: {
                "org.bluez.GattService1": {
                    "UUID": SERVICE_UUID,
                    "Primary": True,
                }
            },
            CHALLENGE_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": CHAR_CHALLENGE,
                    "Service": dbus.ObjectPath(SERVICE_PATH),
                    "Flags": ["write"],
                }
            },
            RESPONSE_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": CHAR_RESPONSE,
                    "Service": dbus.ObjectPath(SERVICE_PATH),
                    "Flags": ["read"],
                }
            },
        }
        return managed_objects


def start_gatt_server():
    """Startet den GATT-Server (mit gültigem ObjectManager)."""
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = bus.get_object("org.bluez", ADAPTER_PATH)
    gatt_manager = dbus.Interface(adapter, "org.bluez.GattManager1")

    app = Application(bus)

    print("Registriere GATT-Service...")
    try:
        gatt_manager.RegisterApplication(app.path, {},
            reply_handler=lambda: print(f"GATT-Service aktiv – UUID: {SERVICE_UUID}"),
            error_handler=lambda e: print("Fehler bei RegisterApplication:", e))
    except Exception as e:
        print("Ausnahme beim Start:", e)
        return None

    return GLib.MainLoop()
