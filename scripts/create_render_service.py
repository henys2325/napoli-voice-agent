"""
Script para crear el Web Service de Napoli Voice Agent en Render.com via API
"""
import requests
import json
import os

RENDER_API_KEY = "rnd_slggXkYx9PiIPkDaLYqayuPdTZ34"
GITHUB_REPO = "https://github.com/henys2325/napoli-voice-agent"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Content-Type": "application/json"
}

# 1. Obtener el owner ID
print("=== Obteniendo Owner ID ===")
resp = requests.get("https://api.render.com/v1/owners?limit=1", headers=headers)
owners = resp.json()
print(json.dumps(owners, indent=2))

owner_id = None
for item in owners:
    if isinstance(item, dict) and "owner" in item:
        owner_id = item["owner"]["id"]
        print(f"Owner ID: {owner_id}")
        break
    elif isinstance(item, dict) and "id" in item:
        owner_id = item["id"]
        print(f"Owner ID: {owner_id}")
        break

if not owner_id:
    print("ERROR: No se pudo obtener el owner ID")
    exit(1)

# 2. Crear el Web Service
print("\n=== Creando Web Service en Render ===")

service_payload = {
    "type": "web_service",
    "name": "napoli-voice-agent",
    "ownerId": owner_id,
    "repo": GITHUB_REPO,
    "branch": "main",
    "rootDir": "",
    "serviceDetails": {
        "plan": "free",
        "region": "oregon",
        "runtime": "python",
        "envSpecificDetails": {
            "buildCommand": "pip install -r requirements.txt",
            "startCommand": "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
        }
    },
    "envVars": [
        {"key": "CLOVER_MERCHANT_ID", "value": "MRWSQWMCDSHQ1"},
        {"key": "CLOVER_API_KEY", "value": "2148cad7-875f-f420-714a-1b29c5af924c"},
        {"key": "CLOVER_BASE_URL", "value": "https://api.clover.com"},
        {"key": "CLOVER_HCO_URL", "value": "https://checkout.clover.com/v1/checkouts"},
        {"key": "VAPI_PRIVATE_KEY", "value": "53c7c8bc-9b72-410f-b4b1-606942ff77f1"},
        {"key": "VAPI_PUBLIC_KEY", "value": "e6b08746-40d3-4abf-926b-d3d87cef25f2"},
        {"key": "VAPI_ASSISTANT_ID", "value": "1350377e-c62e-41e7-85c8-e7ee3254461e"},
        {"key": "TWILIO_ACCOUNT_SID", "value": "AC7c24b545411271286963ec63b0516a762"},
        {"key": "TWILIO_AUTH_TOKEN", "value": "557355d63ef7d3d6d62f04b18e75e20a"},
        {"key": "TWILIO_PHONE_NUMBER", "value": "+17022912025"},
        {"key": "TAX_RATE", "value": "0.08375"},
        {"key": "RESTAURANT_NAME", "value": "Napoli Pizzeria North Las Vegas"},
        {"key": "RESTAURANT_PHONE", "value": "+17252040379"},
        {"key": "PYTHON_VERSION", "value": "3.11.0"}
    ]
}

resp = requests.post(
    "https://api.render.com/v1/services",
    headers=headers,
    json=service_payload
)

print(f"Status: {resp.status_code}")
result = resp.json()
print(json.dumps(result, indent=2))

if resp.status_code in [200, 201]:
    service_id = result.get("service", {}).get("id") or result.get("id")
    service_url = result.get("service", {}).get("serviceDetails", {}).get("url") or \
                  result.get("serviceDetails", {}).get("url", "pending...")
    print(f"\n✅ Servicio creado!")
    print(f"Service ID: {service_id}")
    print(f"URL: {service_url}")
else:
    print(f"\n❌ Error al crear el servicio: {resp.status_code}")
