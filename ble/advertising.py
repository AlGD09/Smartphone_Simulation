#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

ADAPTER_PATH = "/org/bluez/hci0"
ADV_PATH = "/org/bluez/example/advertisement0"

COMPANY_ID = 0xFFFF
DATA = [0x03, 0x8F]
DEVICE_NAME = "Xiaomi"

# D-Bus vorbereiten
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

class Advertisement(dbus.service.Object):
    """
    Korrektes BLE-Advertisement-Objekt für BlueZ ≥ 5.64
    """
    def __init__(self, bus, path):
        self.path = path
        self.bus = bus
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == "org.bluez.LEAdvertisement1":
            props = {
                "Type": dbus.String("peripheral"),
                "LocalName": dbus.String(DEVICE_NAME),
                "ManufacturerData": dbus.Dictionary({
                    dbus.UInt16(COMPANY_ID): dbus.Array(DATA, signature="y")
                }, signature="qv"),
                "IncludeTxPower": dbus.Boolean(False),
            }
            return props
        return {}

    @dbus.service.method("org.bluez.LEAdvertisement1", in_signature="", out_signature="")
    def Release(self):
        print("Advertisement released")

    @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    def get_path(self):
        return dbus.ObjectPath(self.path)


# Adapter- und Advertising-Manager holen
adapter = bus.get_object("org.bluez", ADAPTER_PATH)
ad_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")

adv = Advertisement(bus, ADV_PATH)

# Advertisement registrieren
try:
    ad_manager.RegisterAdvertisement(adv.get_path(), {},
        reply_handler=lambda: print(f"✅ Advertising aktiv – Name: {DEVICE_NAME}, Manufacturer: 0x{COMPANY_ID:04X}, Data: {bytes(DATA).hex()}"),
        error_handler=lambda e: print("❌ Fehler bei RegisterAdvertisement:", e))
except Exception as e:
    print("❌ Ausnahme beim Start:", e)

loop = GLib.MainLoop()
try:
    loop.run()
except KeyboardInterrupt:
    print("\n🛑 Advertising gestoppt.")
