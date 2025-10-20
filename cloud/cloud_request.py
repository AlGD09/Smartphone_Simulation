import requests
import json

class CloudClient:
    def __init__(self, base_url="http://localhost:8080/api/devices/request"):
        self.base_url = base_url

    def request_token(self, device_id: str, secret_hash: str) -> str:
        """
        Sendet die Geräteinformationen an die Cloud und gibt den Token zurück.
        """
        headers = {"Content-Type": "application/json"}
        payload = {
            "deviceId": device_id,
            "secretHash": secret_hash
        }

        try:
            response = requests.post(self.base_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[CloudClient] Fehler bei der Anfrage: {e}")
            return None

        # Antwort auswerten
        try:
            data = response.json()
            token = data.get("token") or data.get("auth_token")
            if not token:
                print(f"[CloudClient] Unerwartete Antwort: {data}")
            return token
        except ValueError:
            print("[CloudClient] Antwort war kein JSON.")
            return None
