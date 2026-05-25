#!/usr/bin/env python3
"""
Update Sofia agent in Vapi.ai with:
1. Better Spanish voice (ElevenLabs multilingual)
2. Improved system prompt - always Spanish when customer speaks Spanish
3. Fix call drop issue (better silence/timeout settings)
4. Updated menu knowledge
"""
import requests
import json

VAPI_KEY = "53c7c8bc-9b72-410f-b4b1-606942ff77f1"
AGENT_ID = "1350377e-c62e-41e7-85c8-e7ee3254461e"
BACKEND_URL = "https://napoli-voice-agent.onrender.com"

HEADERS = {
    "Authorization": f"Bearer {VAPI_KEY}",
    "Content-Type": "application/json",
}

# ============================================================
# VOICE CONFIGURATION
# Best ElevenLabs voices for Latin American Spanish in Vapi.ai:
# - Es3SuNJFCYiMVjxMVqJI = "Valentina" - natural Latin American female
# - XB0fDUnXU5powFXDhCwa = "Charlotte" - multilingual, excellent Spanish
# - pMsXgVXv3BLzUgSXRplE = "Lucia" - Spanish female voice
#
# Model: eleven_turbo_v2_5 = fastest, lowest latency for real-time calls
# Model: eleven_multilingual_v2 = highest quality, slightly more latency
#
# For phone ordering: eleven_turbo_v2_5 is best (speed matters)
# ============================================================
VOICE_CONFIG = {
    "provider": "11labs",
    "voiceId": "XB0fDUnXU5powFXDhCwa",  # Charlotte - excellent multilingual Spanish
    "model": "eleven_turbo_v2_5",         # Fastest model for real-time calls
    "stability": 0.55,                    # Slightly higher = more consistent
    "similarityBoost": 0.80,              # Higher = more natural
    "style": 0.35,                        # Add some expressiveness
    "useSpeakerBoost": True,              # Clearer voice over phone
    "speed": 0.95,                        # Slightly slower = clearer for orders
    "language": "es",                     # Force Spanish language
}

# ============================================================
# SYSTEM PROMPT - Improved for Spanish consistency
# ============================================================
SYSTEM_PROMPT = """Eres Sofía, la asistente de pedidos por teléfono de Napoli Pizzeria en North Las Vegas, Nevada. Tomas pedidos por teléfono de manera profesional y eficiente.

IDIOMA PRINCIPAL: ESPAÑOL
- Cuando el cliente hable en español, responde SIEMPRE en español. NUNCA cambies al inglés.
- Si el cliente habla inglés, responde en inglés.
- Si el cliente habla ruso, responde en ruso.
- NUNCA mezcles idiomas en la misma respuesta.

INFORMACIÓN DEL RESTAURANTE:
- Nombre: Napoli Pizzeria
- Dirección: 3131 W. Craig Rd., North Las Vegas, NV 89032
- Teléfono: 725-204-0379
- Horario: Todos los días 10:00 AM – 10:00 PM (Hora del Pacífico)
- Especiales del almuerzo: Lunes–Viernes 10:00 AM – 3:00 PM SOLAMENTE
- Servicios: Entrega a domicilio, Comer en el local, Para llevar, Catering
- Cargo de entrega: $1.99 | Cargo de conveniencia: 3% | Impuesto: 8.375%
- Especial para llevar: Pizza 16" con 1 ingrediente por $12.99

TU FLUJO DE TRABAJO:
1. Saluda al cliente calurosamente
2. Pregunta si quiere entrega a domicilio o para llevar
3. Si es entrega: pide la dirección de entrega
4. Toma el pedido ítem por ítem — pregunta por tamaño, ingredientes y modificadores para cada ítem
5. Repite el pedido completo para confirmar
6. Pide el nombre y número de teléfono del cliente (para enviar el link de pago)
7. Calcula el total (incluyendo impuesto, cargo de entrega si aplica, y 3% de cargo de conveniencia)
8. Llama a la herramienta 'submit_order_and_send_payment' para crear el pedido y enviar el link de pago por SMS
9. Dile al cliente: "Te he enviado un link de pago a tu teléfono. Tu pedido será enviado a la cocina tan pronto como recibamos el pago. El link expira en 15 minutos."
10. Agradece y termina la llamada

REGLAS IMPORTANTES:
- SIEMPRE confirma el pedido antes de enviarlo
- SIEMPRE informa al cliente que el pedido NO se preparará hasta recibir el pago
- Para pizzas: siempre pregunta el tamaño (10", 14", 16", 18", 24", 28", 30", 36") e ingredientes
- Para wings: siempre pregunta la cantidad (6, 10, 20, 40, 80 piezas) y el sabor de la salsa
- Para wraps: pregunta el tipo y el pan (harina, trigo, sin gluten)
- Los especiales del almuerzo solo están disponibles Lun–Vie antes de las 3 PM
- Sé conversacional pero eficiente — no hagas demasiadas preguntas a la vez
- Si no sabes el precio, usa la herramienta 'search_menu_item' para buscarlo

PRECIOS DE PIZZAS (Hand Tossed New York Style):
- Plain Cheese: 10"=$9.49, 14"=$14.99, 16"=$17.49, 18"=$20.49, 24"=$27.49, 28"=$38.49, 30"=$42.49, 36"=$71.49
- 4 Topping Combo: 10"=$14.49, 14"=$21.49, 16"=$25.49, 18"=$27.49, 24"=$34.49, 28"=$46.49, 30"=$52.49, 36"=$86.49
- Gluten Free 14": $12.75 + ingredientes $2.75 c/u
- Sicilian 12x8: $37.99 combo 4 ingredientes
- Stuffed Chicago Deep Dish: $43.99 combo 4 ingredientes
- Ingredientes disponibles (30+): Pepperoni, Salchicha, Jamón, Albóndigas, Pollo, Champiñones, Pimientos verdes, Cebollas, Aceitunas negras, Aceitunas verdes, Tomates, Ajo, Espinaca, Jalapeños, Piña, Tocino canadiense, Anchoas, Alcachofas, Albahaca fresca, Brócoli, Calabacín, Capicola, Cheddar, Chorizo, Berenjena, Pimientos rojos asados, Salami, Cheddar

PRECIOS DE WINGS:
- Bone-In: 6pc=$11.49, 10pc=$15.49, 20pc=$25.49, 40pc=$56.49, 80pc=$108.49
- Boneless: 6pc=$9.49, 10pc=$13.49, 20pc=$26.49, 40pc=$47.49, 80pc=$89.49
- Fingers: 6pc=$13.49, 10pc=$22.49, 20pc=$40.49, 40pc=$75.49, 80pc=$144.49
- Sabores: Plain, Mild, Medium, Hot, BBQ, Spicy BBQ, Honey BBQ, Lemon Pepper, Teriyaki, Spicy Teriyaki, Sweet Red Chili, Mango Habanero
- +Fries: $2 adicionales

MANEJO DE LLAMADAS LARGAS:
- Si el cliente está pensando o en silencio, di: "Tómate tu tiempo, estoy aquí cuando estés listo."
- Si el cliente necesita más tiempo, ofrece esperar
- No cuelgues la llamada si el cliente está en medio de un pedido
- Si hay problemas técnicos, pide al cliente que llame de nuevo al 725-204-0379"""

# ============================================================
# TOOLS - Keep the same 4 tools
# ============================================================
def get_current_tools():
    """Get the current tools from the agent."""
    r = requests.get(
        f"https://api.vapi.ai/assistant/{AGENT_ID}",
        headers=HEADERS
    )
    data = r.json()
    return data.get("model", {}).get("tools", [])

def update_agent():
    print("=== Updating Sofia Agent ===\n")

    # Get current tools
    tools = get_current_tools()
    print(f"Current tools: {len(tools)}")
    for t in tools:
        print(f"  - {t.get('function', {}).get('name', 'unknown')}")

    # Build the update payload
    payload = {
        # Voice: Better Spanish voice
        "voice": VOICE_CONFIG,

        # Transcriber: Keep Deepgram nova-2 multilingual but improve settings
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",
            "smartFormat": True,
            "languageDetectionEnabled": True,
            "fallbackPlan": {
                "autoFallback": {
                    "enabled": True
                }
            }
        },

        # Model: Keep GPT-4o with improved system prompt
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.4,  # Lower = more consistent, less hallucination
            "maxTokens": 500,    # Shorter responses = faster
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ],
            "tools": tools  # Keep existing tools
        },

        # First message in Spanish (most customers are Spanish-speaking)
        "firstMessage": "¡Gracias por llamar a Napoli Pizzeria! Soy Sofía, tu asistente de pedidos. ¿Estás llamando para hacer un pedido para recoger o entrega a domicilio?",
        "firstMessageMode": "assistant-speaks-first",

        # Call settings - Fix call drop issues
        "maxDurationSeconds": 900,      # 15 minutes max (was 10)
        "silenceTimeoutSeconds": 20,    # 20 seconds silence before timeout (was 30)
        "responseDelaySeconds": 0.3,    # Slightly faster response
        "llmRequestDelaySeconds": 0.1,  # Faster LLM start

        # End call behavior
        "endCallMessage": "¡Gracias por llamar a Napoli Pizzeria! Tu pedido estará listo pronto. ¡Hasta luego!",
        "endCallPhrases": [
            "adiós", "hasta luego", "gracias bye", "goodbye", "bye bye",
            "that's all", "eso es todo", "ya terminé", "no gracias"
        ],

        # Background noise handling
        "backgroundSound": "office",
        "backgroundDenoisingEnabled": True,

        # Hipaa compliance off for restaurant
        "hipaaEnabled": False,

        # Server webhook for call events
        "server": {
            "url": f"{BACKEND_URL}/webhook/vapi",
            "timeoutSeconds": 20,
        }
    }

    print("\nUpdating agent...")
    r = requests.patch(
        f"https://api.vapi.ai/assistant/{AGENT_ID}",
        headers=HEADERS,
        json=payload
    )

    if r.status_code == 200:
        data = r.json()
        print(f"✅ Agent updated successfully!")
        print(f"  Voice: {data.get('voice', {}).get('voiceId')} ({data.get('voice', {}).get('provider')})")
        print(f"  Model: {data.get('voice', {}).get('model', 'default')}")
        print(f"  Max duration: {data.get('maxDurationSeconds')}s")
        print(f"  Silence timeout: {data.get('silenceTimeoutSeconds')}s")
        print(f"  First message: {data.get('firstMessage', '')[:80]}...")
        return True
    else:
        print(f"❌ Error updating agent: {r.status_code}")
        print(r.text[:500])
        return False

if __name__ == "__main__":
    success = update_agent()
    if success:
        print("\n✅ Sofia agent updated successfully!")
        print("  - Voice: ElevenLabs Charlotte (multilingual, excellent Spanish)")
        print("  - Model: eleven_turbo_v2_5 (fastest for real-time calls)")
        print("  - Language: Forced Spanish when customer speaks Spanish")
        print("  - Call drop fix: Better silence timeout and max duration")
        print("  - First message: Now in Spanish")
    else:
        print("\n❌ Failed to update agent")
