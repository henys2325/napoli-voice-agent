"""
Script para desplegar el backend de Napoli Voice Agent en Render.com
usando la Render API directamente (sin necesidad de GitHub).
Estrategia: usar un repositorio público de GitHub con el código.
"""

import requests
import json
import os
import subprocess
import sys

RENDER_API_KEY = "rnd_slggXkYx9PiIPkDaLYqayuPdTZ34"
RENDER_API_BASE = "https://api.render.com/v1"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def get_owner_id():
    """Obtener el ID del workspace/owner en Render"""
    resp = requests.get(f"{RENDER_API_BASE}/owners", headers=headers)
    print(f"Owners status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2)[:500])
        return data[0]["owner"]["id"] if data else None
    else:
        print(f"Error: {resp.text}")
        return None

def list_services():
    """Listar servicios existentes en Render"""
    resp = requests.get(f"{RENDER_API_BASE}/services", headers=headers)
    print(f"Services status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2)[:1000])
        return data
    else:
        print(f"Error: {resp.text}")
        return []

if __name__ == "__main__":
    print("=== Verificando acceso a Render API ===")
    owner_id = get_owner_id()
    print(f"\nOwner ID: {owner_id}")
    
    print("\n=== Servicios existentes ===")
    services = list_services()
    print(f"\nTotal servicios: {len(services)}")
