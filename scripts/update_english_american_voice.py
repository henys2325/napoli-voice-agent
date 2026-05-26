"""
Update Sofia agent English voice to American (Nevada/Southwest USA).

Problem: Current voice (Charlotte XB0fDUnXU5powFXDhCwa) sounds British/European in English.
Solution: Use ElevenLabs "Aria" (9BWtsMINqrJLrRacOk9x) — official ElevenLabs voice,
          warm American female, conversational, multilingual.
          Same cadence/latency settings as Spanish.

Voice selection rationale:
- Aria (9BWtsMINqrJLrRacOk9x): ElevenLabs' flagship American female voice.
  Warm, conversational, natural American accent. Works perfectly for phone ordering.
  Multilingual — handles Spanish/Russian as fallback.
- eleven_turbo_v2_5: Fastest model, same latency as current Spanish setup.
  For English (non-Slavic), turbo is ideal — no quality loss vs multilingual_v2.

Cadence matching Spanish:
- stability: 0.50 (same feel as Charlotte in Spanish)
- similarityBoost: 0.80 (consistent character)
- style: 0.35 (warm, expressive — matches Spanish energy)
- speed: 0.95 (slightly slower = clearer for phone orders, same as Spanish was)
- responseDelaySeconds: 0.2 (identical to Spanish)
- llmRequestDelaySeconds: 0.1 (identical to Spanish)
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
# VOICE — Aria: American female, warm, conversational
# eleven_turbo_v2_5 = fastest, same latency as Spanish setup
# ============================================================
VOICE_CONFIG = {
    "provider": "11labs",
    "voiceId": "9BWtsMINqrJLrRacOk9x",    # Aria — warm American female
    "model": "eleven_turbo_v2_5",           # Fast = same latency as Spanish
    "stability": 0.50,                      # Natural, not robotic
    "similarityBoost": 0.80,                # Consistent voice character
    "style": 0.35,                          # Warm, expressive — matches Spanish energy
    "useSpeakerBoost": True,                # Clearer over phone line
    "speed": 0.95,                          # Slightly slower = clearer for orders
    # No language lock — auto-handles EN/ES/RU
}


def get_current_config():
    """Get the current agent config to preserve tools and prompt."""
    r = requests.get(
        f"https://api.vapi.ai/assistant/{AGENT_ID}",
        headers=HEADERS
    )
    return r.json()


def update_agent():
    print("=== Updating Sofia Agent — American English Voice ===\n")

    current = get_current_config()
    tools = current.get("model", {}).get("tools", [])
    system_prompt = current.get("model", {}).get("messages", [{}])[0].get("content", "")
    first_message = current.get("firstMessage", "")
    end_phrases = current.get("endCallPhrases", [])

    print(f"Preserving {len(tools)} tools")
    print(f"Preserving system prompt ({len(system_prompt)} chars)")
    print(f"Current voice: {current.get('voice', {}).get('voiceId')} / {current.get('voice', {}).get('model')}")
    print(f"New voice: Aria (9BWtsMINqrJLrRacOk9x) / eleven_turbo_v2_5")

    payload = {
        # New voice: Aria (American) with turbo for same latency as Spanish
        "voice": VOICE_CONFIG,

        # Transcriber: keep Deepgram nova-2 multi (auto-detects EN/ES/RU)
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",
            "smartFormat": True,
            "languageDetectionEnabled": True,
        },

        # Model: keep same prompt and tools
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.45,
            "maxTokens": 500,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ],
            "tools": tools
        },

        # Keep same first message and end phrases
        "firstMessage": first_message,
        "firstMessageMode": "assistant-speaks-first",

        # Latency: IDENTICAL to Spanish setup
        "maxDurationSeconds": 900,
        "silenceTimeoutSeconds": 20,
        "responseDelaySeconds": 0.2,       # Same as Spanish
        "llmRequestDelaySeconds": 0.1,     # Same as Spanish

        # End call
        "endCallMessage": "Thanks for calling Napoli Pizzeria! See you soon!",
        "endCallPhrases": end_phrases,

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
        voice = data.get("voice", {})
        print(f"\n✅ Agent updated successfully!")
        print(f"  Voice ID: {voice.get('voiceId')}")
        print(f"  Voice model: {voice.get('model')}")
        print(f"  Stability: {voice.get('stability')}")
        print(f"  Style: {voice.get('style')}")
        print(f"  Speed: {voice.get('speed')}")
        print(f"  Response delay: {data.get('responseDelaySeconds')}s")
        print(f"  LLM delay: {data.get('llmRequestDelaySeconds')}s")
        return True
    else:
        print(f"\n❌ Error: {r.status_code}")
        print(r.text[:600])
        return False


if __name__ == "__main__":
    success = update_agent()
    if success:
        print("\n✅ American English voice applied:")
        print("  - Voice: Aria (ElevenLabs official) — warm American female")
        print("  - Accent: American (Nevada/Southwest USA natural)")
        print("  - Model: eleven_turbo_v2_5 — same latency as Spanish")
        print("  - Cadence: speed=0.95, stability=0.50, style=0.35")
        print("  - Response delay: 0.2s (identical to Spanish)")
        print("  - All other settings preserved (prompt, tools, transcriber)")
    else:
        print("\n❌ Failed to update agent")
