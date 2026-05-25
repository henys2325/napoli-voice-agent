"""
Script para registrar el agente Sofia en Vapi.ai via API REST
"""
import json
import requests
import sys
import os

VAPI_API_KEY = os.getenv("VAPI_PRIVATE_KEY")
BASE_URL_PLACEHOLDER = "https://your-server-domain.com"  # se actualiza después del deploy

headers = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json"
}

# Cargar la configuración del agente
config_path = os.path.join(os.path.dirname(__file__), "../config/vapi_agent_config.json")
with open(config_path) as f:
    raw = f.read().replace("{{BASE_URL}}", BASE_URL_PLACEHOLDER)
    config = json.loads(raw)

# Construir el payload para la API de Vapi
payload = {
    "name": config["name"],
    "model": {
        "provider": config["model"]["provider"],
        "model": config["model"]["model"],
        "temperature": config["model"]["temperature"],
        "messages": [
            {
                "role": "system",
                "content": config["model"]["systemPrompt"]
            }
        ]
    },
    "voice": {
        "provider": config["voice"]["provider"],
        "voiceId": config["voice"]["voiceId"],
        "stability": config["voice"]["stability"],
        "similarityBoost": config["voice"]["similarityBoost"],
        "speed": config["voice"]["speed"]
    },
    "transcriber": {
        "provider": config["transcriber"]["provider"],
        "model": config["transcriber"]["model"],
        "language": config["transcriber"]["language"]
    },
    "firstMessage": config["firstMessage"],
    "firstMessageMode": config["firstMessageMode"],
    "endCallMessage": config["endCallMessage"],
    "endCallPhrases": config["endCallPhrases"],
    "maxDurationSeconds": config["maxDurationSeconds"],
    "silenceTimeoutSeconds": config["silenceTimeoutSeconds"],
    "responseDelaySeconds": config["responseDelaySeconds"],
    "backchannelingEnabled": config["backchannelingEnabled"],
    "backgroundDenoisingEnabled": config["backgroundDenoisingEnabled"],
    "backgroundSound": "off",
    "startSpeakingPlan": config["startSpeakingPlan"],
    "stopSpeakingPlan": config["stopSpeakingPlan"],
    "analysisPlan": config["analysisPlan"]
}

print("🤖 Registrando agente Sofia en Vapi.ai...")
print(f"   Nombre: {payload['name']}")
print(f"   Modelo: {payload['model']['model']}")
print(f"   Voz: {payload['voice']['provider']} / {payload['voice']['voiceId']}")
print(f"   Idiomas: {payload['transcriber']['language']}")
print()

response = requests.post(
    "https://api.vapi.ai/assistant",
    headers=headers,
    json=payload,
    timeout=30
)

if response.status_code in (200, 201):
    data = response.json()
    assistant_id = data.get("id")
    print(f"✅ Agente creado exitosamente!")
    print(f"   Assistant ID: {assistant_id}")
    print(f"   Nombre: {data.get('name')}")
    print()
    print(f"📝 Agrega esta línea a tu .env:")
    print(f"   VAPI_ASSISTANT_ID={assistant_id}")
    
    # Guardar el ID en un archivo para referencia
    with open(os.path.join(os.path.dirname(__file__), "../config/vapi_assistant_id.txt"), "w") as f:
        f.write(assistant_id)
    print()
    print("✅ ID guardado en config/vapi_assistant_id.txt")
else:
    print(f"❌ Error al crear el agente: {response.status_code}")
    print(f"   Respuesta: {response.text[:500]}")
    sys.exit(1)
