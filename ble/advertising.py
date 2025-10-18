#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

# Pfad des aktiven Bluetooth-Adapters (bei dir hci1)
ADAPTER_PATH = "/org/bluez/hci1"
ADV_PATH = "/org/bluez/example/advertisement0"

# Daten, die beworben werden sollen
COMPANY_ID = 0xFFFF
DATA = [0x03, 0x8F]
DEVICE_NAME = "Xiaomi"

# D-Bus vorbereiten
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
loop = None
ad_manager = None
adv = None


class Advertisement(dbus.service.Object):
    """Korrektes BLE-Advertisement-Objekt für BlueZ ≥ 5.64"""

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


def start_advertising():
    """Startet BLE Advertising."""
    global ad_manager, adv, loop

    adapter = bus.get_object("org.bluez", ADAPTER_PATH)
    ad_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")

    adv = Advertisement(bus, ADV_PATH)
    loop = GLib.MainLoop()

    try:
        ad_manager.RegisterAdvertisement(
            adv.get_path(),
            dbus.Dictionary({}, signature="sv"),
            reply_handler=lambda: print(f"✅ Advertising aktiv – Name: {DEVICE_NAME}, Manufacturer: 0x{COMPANY_ID:04X}, Data: {bytes(DATA).hex()}"),
            error_handler=lambda e: print("❌ Fehler bei RegisterAdvertisement:", e)
        )
    except Exception as e:
        print("❌ Ausnahme beim Start:", e)
        return

    try:
        loop.run()
    except KeyboardInterrupt:
        stop_advertising()


def stop_advertising():
    """Stoppt BLE Advertising."""
    global ad_manager, adv, loop

    if ad_manager and adv:
        try:
            ad_manager.UnregisterAdvertisement(adv.get_path())
            print("🛑 Advertising gestoppt.")
        except Exception as e:
            if "UnknownObject" not in str(e):
                print("⚠️ Fehler beim Stoppen:", e)

    if loop:
        loop.quit()


# Wenn Skript direkt ausgeführt wird
if __name__ == "__main__":
    start_advertising()
