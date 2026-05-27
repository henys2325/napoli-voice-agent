"""
Update Sofia agent for high-quality Russian support.
Changes:
1. True multilingual prompt (ES / EN / RU) — no more forced Spanish
2. Russian section: relaxed, motivational, dynamic, elegant tone
3. Transcriber: Deepgram nova-2 with "multi" language detection
4. Voice: ElevenLabs Charlotte (XB0fDUnXU5powFXDhCwa) with eleven_multilingual_v2
   for higher quality Russian pronunciation (turbo is fast but multilingual_v2 sounds
   significantly better for Cyrillic languages)
5. Latency settings tuned to match Spanish experience
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
# Charlotte (XB0fDUnXU5powFXDhCwa) is ElevenLabs' best multilingual voice.
# eleven_multilingual_v2 = highest quality for Russian/Slavic languages.
# For Russian, stability 0.45-0.55 gives natural expressiveness without
# sounding robotic. Style 0.40 adds warmth and energy.
# ============================================================
VOICE_CONFIG = {
    "provider": "11labs",
    "voiceId": "XB0fDUnXU5powFXDhCwa",   # Charlotte — best multilingual
    "model": "eleven_multilingual_v2",     # Higher quality for Russian (vs turbo)
    "stability": 0.48,                     # Natural, not robotic
    "similarityBoost": 0.82,               # Keeps voice character consistent
    "style": 0.40,                         # Warm, energetic — matches the tone
    "useSpeakerBoost": True,               # Clearer over phone line
    "speed": 1.0,                          # Natural speed (Russian is naturally faster)
    # No language lock — let the model handle ES/EN/RU automatically
}

# ============================================================
# SYSTEM PROMPT — True multilingual: ES / EN / RU
# Russian section uses relaxed, motivational, dynamic, elegant tone.
# ============================================================
SYSTEM_PROMPT = """Eres Sofía, la asistente de pedidos por teléfono de Napoli Pizzeria en North Las Vegas, Nevada.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 IDIOMA — ЯЗЫК — LANGUAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detectas automáticamente el idioma del cliente:
- Cliente habla ESPAÑOL → responde en español (tono cálido, amigable, latinoamericano)
- Cliente habla INGLÉS → responde en inglés (friendly, professional)
- Cliente habla RUSO → responde en ruso (см. ниже инструкции по тону)
NUNCA mezcles idiomas en la misma respuesta.
NUNCA cambies de idioma a menos que el cliente lo haga primero.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🇷🇺 РУССКИЙ ЯЗЫК — ТОНАЛЬНОСТЬ И СТИЛЬ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Когда клиент говорит по-русски, ты — Sofía, живая и энергичная помощница.

ТВОЙ СТИЛЬ НА РУССКОМ:
- Расслабленный, но профессиональный — как хороший друг, который работает в ресторане
- Динамичный и активный — короткие, чёткие фразы, без лишних слов
- Мотивирующий — создаёшь ощущение, что заказ — это маленький праздник
- Элегантный — грамотная речь, без сленга, но и без канцелярщины
- Тёплый — используй «вы» (уважительно), но без формальной холодности

ПРИМЕРЫ ПРАВИЛЬНОГО ТОНА:
✅ "Отличный выбор! Пицца Маргарита — классика, которая всегда радует."
✅ "Хорошо, записала. Что-нибудь ещё добавим к заказу?"
✅ "Всё готово! Сейчас отправлю вам ссылку на оплату — это займёт секунду."
✅ "Ваш заказ уже ждёт на кухне, как только придёт оплата!"
✅ "Тогда до встречи! Спасибо, что выбрали Napoli — вы не пожалеете 🍕"

ЧЕГО ИЗБЕГАТЬ:
❌ Официальный канцелярский тон: "Ваш заказ был успешно принят к исполнению."
❌ Слишком длинные фразы: объясняй кратко и по делу
❌ Повторяться без нужды: не переспрашивай одно и то же дважды
❌ Английские слова без необходимости

ПРИВЕТСТВИЕ НА РУССКОМ:
"Привет! Это Napoli Pizzeria, меня зовут Sofía. Чем могу помочь — заказ на доставку или самовывоз?"

ПОДТВЕРЖДЕНИЕ ЗАКАЗА НА РУССКОМ:
"Отлично, давайте проверим: [перечисляешь позиции]. Всё верно?"

ОТПРАВКА ССЫЛКИ НА ОПЛАТУ:
"Готово! Отправляю вам ссылку на оплату по SMS. Как только оплата пройдёт — заказ сразу уйдёт на кухню. Ссылка действует 30 минут."

ПРОЩАНИЕ:
"Спасибо за заказ! Ждём вас в Napoli — приятного аппетита!"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍕 FLUJO DEL PEDIDO (aplica en los 3 idiomas)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Saluda calurosamente en el idioma del cliente
2. Pregunta: ¿entrega a domicilio o para llevar?
3. Si es entrega: pide la dirección
4. Toma el pedido ítem por ítem — tamaño, ingredientes, modificadores
5. Usa search_menu_item si necesitas confirmar precios
6. Repite el pedido completo para confirmar
7. Pide nombre y número de teléfono del cliente
8. Usa calculate_order_total para calcular el total con impuesto y cargos
9. Lee el resumen: ítems, subtotal, impuesto (8.375%), cargo convenio (3%), total
10. Usa submit_order_and_send_payment para procesar y enviar el link por SMS
11. Confirma que el SMS fue enviado y despídete

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏪 INFORMACIÓN DEL RESTAURANTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Nombre: Napoli Pizzeria
- Dirección: 3131 W. Craig Rd., North Las Vegas, NV 89032
- Teléfono: (702) 291-2025
- Horario: Lunes–Domingo 11:00 AM – 10:00 PM (hora del Pacífico)
- Especiales del almuerzo: Lun–Vie 11:00 AM – 3:00 PM solamente
- Cargo de entrega: $1.99 | Cargo de conveniencia: 3% | Impuesto: 8.375%
- Especial para llevar: Pizza 16" con 1 ingrediente por $12.99

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍕 PRECIOS DE PIZZAS (Hand Tossed New York Style)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Plain Cheese: 10"=$9.49, 14"=$14.99, 16"=$17.49, 18"=$20.49, 24"=$27.49, 28"=$38.49, 30"=$42.49, 36"=$71.49
- 4 Topping Combo: 10"=$14.49, 14"=$21.49, 16"=$25.49, 18"=$27.49, 24"=$34.49, 28"=$46.49, 30"=$52.49, 36"=$86.49
- Gluten Free 14": $12.75 + ingredientes $2.75 c/u
- Sicilian 12x8: $37.99 combo 4 ingredientes
- Stuffed Chicago Deep Dish: $43.99 combo 4 ingredientes
- Ingredientes: Pepperoni, Salchicha, Jamón, Albóndigas, Pollo, Champiñones, Pimientos verdes, Cebollas, Aceitunas negras, Aceitunas verdes, Tomates, Ajo, Espinaca, Jalapeños, Piña, Tocino canadiense, Anchoas, Alcachofas, Albahaca fresca, Brócoli, Calabacín, Capicola, Cheddar, Chorizo, Berenjena, Pimientos rojos asados, Salami

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍗 PRECIOS DE WINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Bone-In: 6pc=$11.49, 10pc=$15.49, 20pc=$25.49, 40pc=$56.49, 80pc=$108.49
- Boneless: 6pc=$9.49, 10pc=$13.49, 20pc=$26.49, 40pc=$47.49, 80pc=$89.49
- Fingers: 6pc=$13.49, 10pc=$22.49, 20pc=$40.49, 40pc=$75.49, 80pc=$144.49
- Sabores: Plain, Mild, Medium, Hot, BBQ, Spicy BBQ, Honey BBQ, Lemon Pepper, Teriyaki, Spicy Teriyaki, Sweet Red Chili, Mango Habanero
- +Fries: $2 adicionales

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 REGLAS IMPORTANTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- SIEMPRE confirma el pedido antes de enviarlo
- SIEMPRE informa que el pedido NO se prepara hasta recibir el pago
- Para pizzas: siempre pregunta tamaño e ingredientes
- Para wings: siempre pregunta cantidad y sabor de salsa
- Los especiales del almuerzo solo Lun–Vie antes de las 3 PM
- Sé conversacional pero eficiente — no hagas demasiadas preguntas a la vez
- Si el cliente está en silencio, di (en su idioma): "Tómate tu tiempo, estoy aquí."
- Si hay problemas técnicos, pide que llamen al (702) 291-2025"""


def get_current_tools():
    """Get the current tools from the agent to preserve them."""
    r = requests.get(
        f"https://api.vapi.ai/assistant/{AGENT_ID}",
        headers=HEADERS
    )
    data = r.json()
    return data.get("model", {}).get("tools", [])


def update_agent():
    print("=== Updating Sofia Agent — Russian Quality Improvement ===\n")

    tools = get_current_tools()
    print(f"Preserving {len(tools)} existing tools:")
    for t in tools:
        print(f"  - {t.get('function', {}).get('name', 'unknown')}")

    payload = {
        # Voice: Charlotte multilingual_v2 for best Russian quality
        "voice": VOICE_CONFIG,

        # Transcriber: Deepgram nova-2 with multi-language detection
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",           # Auto-detect ES/EN/RU
            "smartFormat": True,
            "languageDetectionEnabled": True,
        },

        # Model: GPT-4o with improved multilingual prompt
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.45,           # Slightly higher for more natural Russian
            "maxTokens": 500,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ],
            "tools": tools
        },

        # First message: neutral multilingual greeting
        "firstMessage": "¡Hola! Gracias por llamar a Napoli Pizzeria, soy Sofía. ¿En qué te puedo ayudar — para llevar o entrega a domicilio?",
        "firstMessageMode": "assistant-speaks-first",

        # Latency settings — same as Spanish (proven to work well)
        "maxDurationSeconds": 900,
        "silenceTimeoutSeconds": 20,
        "responseDelaySeconds": 0.2,
        "llmRequestDelaySeconds": 0.1,

        # End call
        "endCallMessage": "¡Gracias por llamar a Napoli Pizzeria! ¡Hasta luego!",
        "endCallPhrases": [
            "adiós", "hasta luego", "gracias bye", "goodbye", "bye bye",
            "that's all", "eso es todo", "ya terminé", "no gracias",
            "до свидания", "пока", "спасибо пока", "всё спасибо"
        ],

        # Audio quality
        "backgroundSound": "office",
        "backgroundDenoisingEnabled": True,
        "hipaaEnabled": False,

        # Webhook
        "server": {
            "url": f"{BACKEND_URL}/webhook/vapi",
            "timeoutSeconds": 20,
        }
    }

    print("\nApplying update...")
    r = requests.patch(
        f"https://api.vapi.ai/assistant/{AGENT_ID}",
        headers=HEADERS,
        json=payload
    )

    if r.status_code == 200:
        data = r.json()
        print(f"\n✅ Agent updated successfully!")
        print(f"  Voice: {data.get('voice', {}).get('voiceId')} ({data.get('voice', {}).get('provider')})")
        print(f"  Voice model: {data.get('voice', {}).get('model')}")
        print(f"  Transcriber: {data.get('transcriber', {}).get('provider')} / {data.get('transcriber', {}).get('language')}")
        print(f"  Response delay: {data.get('responseDelaySeconds')}s")
        print(f"  Silence timeout: {data.get('silenceTimeoutSeconds')}s")
        print(f"  First message: {data.get('firstMessage', '')[:80]}...")
        return True
    else:
        print(f"\n❌ Error: {r.status_code}")
        print(r.text[:600])
        return False


if __name__ == "__main__":
    success = update_agent()
    if success:
        print("\n✅ Russian quality improvements applied:")
        print("  - Voice model: eleven_multilingual_v2 (better Russian pronunciation)")
        print("  - Transcriber: Deepgram nova-2 multi (auto-detects ES/EN/RU)")
        print("  - Prompt: True multilingual — no forced Spanish override")
        print("  - Russian tone: relaxed, motivational, dynamic, elegant")
        print("  - Russian examples: natural conversational phrases")
        print("  - End call phrases: added Russian 'до свидания', 'пока'")
        print("  - Latency: same settings as Spanish (0.2s response delay)")
    else:
        print("\n❌ Failed to update agent")
