"""
Script de verificación completa de todas las conexiones del sistema.
Verifica: Backend Render, Clover API (via backend), Vapi.ai, Twilio
Credenciales se leen desde variables de entorno o .env
"""
import requests
import json
import os
from dotenv import load_dotenv

# Load from .env if present
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

BACKEND_URL = os.getenv("BACKEND_URL", "https://napoli-voice-agent.onrender.com")
VAPI_KEY = os.getenv("VAPI_API_KEY", "")
ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "1350377e-c62e-41e7-85c8-e7ee3254461e")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

results = {}

print("=" * 60)
print("VERIFICACIÓN COMPLETA DEL SISTEMA — NAPOLI PIZZERIA AI")
print("=" * 60)

# 1. Backend Render
print("\n[1/5] Backend (Render.com)...")
try:
    r = requests.get(f"{BACKEND_URL}/health", timeout=30)
    if r.status_code == 200:
        data = r.json()
        print(f"  ✅ ONLINE — {data.get('service','?')} | {data.get('timestamp','')[:19]}")
        results["backend"] = "OK"
    else:
        print(f"  ❌ ERROR {r.status_code}")
        results["backend"] = f"ERROR {r.status_code}"
except Exception as e:
    print(f"  ❌ TIMEOUT/ERROR: {e}")
    results["backend"] = "TIMEOUT"

# 2. Menú desde Clover (via backend)
print("\n[2/5] Menú de Clover (via backend)...")
try:
    r = requests.get(f"{BACKEND_URL}/menu", timeout=30)
    if r.status_code == 200:
        data = r.json()
        cats = data.get("categories", {})
        mods_count = len(data.get("modifier_groups", {}))
        total_items = sum(len(c.get("items", [])) for c in cats.values())
        print(f"  ✅ CONECTADO — {len(cats)} categorías | {total_items} ítems | {mods_count} grupos de modificadores")
        for cat_name in list(cats.keys())[:8]:
            cat_items = cats[cat_name].get("items", [])
            print(f"     • {cat_name}: {len(cat_items)} ítems")
        results["clover_menu"] = f"OK - {total_items} items"
    else:
        print(f"  ❌ ERROR {r.status_code}: {r.text[:100]}")
        results["clover_menu"] = f"ERROR {r.status_code}"
except Exception as e:
    print(f"  ❌ ERROR: {e}")
    results["clover_menu"] = "ERROR"

# 3. Vapi.ai — Agente Sofia
print("\n[3/5] Agente Sofia (Vapi.ai)...")
if not VAPI_KEY:
    print("  ⚠️  VAPI_API_KEY no configurada en .env")
    results["vapi"] = "NO_KEY"
else:
    try:
        r = requests.get(
            f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
            headers={"Authorization": f"Bearer {VAPI_KEY}"},
            timeout=20
        )
        if r.status_code == 200:
            data = r.json()
            name = data.get("name", "?")
            voice = data.get("voice", {}).get("voiceId", "?")
            model = data.get("model", {}).get("model", "?")
            tools = data.get("model", {}).get("tools", [])
            print(f"  ✅ ACTIVO — Nombre: {name}")
            print(f"     Modelo: {model} | Voz: {voice}")
            print(f"     Herramientas: {len(tools)} configuradas")
            for t in tools:
                fn = t.get("function", {})
                print(f"     • {fn.get('name','?')}: {fn.get('description','')[:60]}")
            results["vapi"] = "OK"
        else:
            print(f"  ❌ ERROR {r.status_code}: {r.text[:100]}")
            results["vapi"] = f"ERROR {r.status_code}"
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        results["vapi"] = "ERROR"

# 4. Twilio — Número de teléfono
print("\n[4/5] Twilio — Número de teléfono...")
if not TWILIO_SID or not TWILIO_TOKEN:
    print("  ⚠️  TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN no configurados en .env")
    results["twilio"] = "NO_KEY"
else:
    try:
        r = requests.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/IncomingPhoneNumbers.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            timeout=20
        )
        if r.status_code == 200:
            data = r.json()
            numbers = data.get("incoming_phone_numbers", [])
            print(f"  ✅ CONECTADO — {len(numbers)} número(s) activo(s)")
            for n in numbers:
                print(f"     • {n.get('friendly_name','?')} — {n.get('phone_number','?')}")
            results["twilio"] = "OK"
        else:
            print(f"  ❌ ERROR {r.status_code}: {r.text[:100]}")
            results["twilio"] = f"ERROR {r.status_code}"
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        results["twilio"] = "ERROR"

# 5. Verificar que el número de Twilio está conectado a Vapi
print("\n[5/5] Verificando conexión Twilio → Vapi.ai...")
if VAPI_KEY:
    try:
        r = requests.get(
            "https://api.vapi.ai/phone-number",
            headers={"Authorization": f"Bearer {VAPI_KEY}"},
            timeout=20
        )
        if r.status_code == 200:
            numbers = r.json()
            if isinstance(numbers, list) and numbers:
                for n in numbers:
                    num = n.get("number", "?")
                    assistant = n.get("assistantId", n.get("assistant", {}).get("id", "?"))
                    print(f"  ✅ CONECTADO — {num} → Assistant: {assistant}")
                results["phone_link"] = "OK"
            else:
                print(f"  ⚠️  Sin números registrados en Vapi")
                results["phone_link"] = "NO_NUMBERS"
        else:
            print(f"  ❌ ERROR {r.status_code}: {r.text[:100]}")
            results["phone_link"] = f"ERROR {r.status_code}"
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        results["phone_link"] = "ERROR"

# Resumen final
print("\n" + "=" * 60)
print("RESUMEN DEL SISTEMA:")
all_ok = all(v == "OK" or v.startswith("OK") for v in results.values())
for component, status in results.items():
    icon = "✅" if (status == "OK" or status.startswith("OK")) else "❌"
    print(f"  {icon} {component.upper()}: {status}")

if all_ok:
    print("\n🎉 TODOS LOS SISTEMAS OPERATIVOS — El agente está listo para recibir llamadas")
else:
    print("\n⚠️  Algunos componentes requieren atención")
print("=" * 60)
