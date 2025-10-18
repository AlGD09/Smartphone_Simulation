#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

# Passe den Adapter an (prüfe mit: hciconfig)
ADAPTER_PATH = "/org/bluez/hci1"
SERVICE_UUID = "0000aaa0-0000-1000-8000-aabbccddeeff"

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# BlueZ-Objekte holen
adapter = bus.get_object("org.bluez", ADAPTER_PATH)
gatt_manager = dbus.Interface(adapter, "org.bluez.GattManager1")

# Einfaches Dummy-Service-Objekt
class DummyService(dbus.service.Object):
    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)
        self.path = path
    def get_path(self):
        return dbus.ObjectPath(self.path)

service = DummyService(bus, "/org/bluez/example/service0")

try:
    gatt_manager.RegisterApplication(
        "/org/bluez/example",
        {},
        reply_handler=lambda: print("✅ GATT-Registrierung erfolgreich!"),
        error_handler=lambda e: print("❌ Fehler bei RegisterApplication:", e),
    )
except Exception as e:
    print("❌ Ausnahme:", e)

GLib.MainLoop().run()
