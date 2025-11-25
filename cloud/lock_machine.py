import requests
import json


class LockMachine: 
    def __init__(self, base_url="http://localhost:8080/api/rcu/lock/", request_timeout: float = 11.0):
        self.base_url = base_url
        self.request_timeout = request_timeout

    def lock_machine(self, rcuId: str, deviceName: str, deviceId: str) -> str: 
        headers = {"Content-Type": "application/json"}
        payload = {
            "rcuId": rcuId, 
            "deviceName": deviceName, 
            "deviceId": deviceId
        }

        try: 
            response = requests.post(
                self.base_url + rcuId,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            print("Lock an Cloud gesendet")
        except requests.exceptions.RequestException as e:
            print(f"[CloudClient] Fehler bei der Lock-Anfrage: {e}")
            return False
        
        try:
            data = response.json()
            status = data.get("status")
            print(status)
            if not status:
                print(f"[CloudClient] Unerwartete Antwort: {data}")
            return True
        except ValueError:
            print("[CloudClient] Antwort war kein JSON.")
            return False
