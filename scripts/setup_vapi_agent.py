"""
Setup script to create/update the Napoli Pizzeria voice agent on Vapi.ai.
Run this once after setting your VAPI_API_KEY and BASE_URL in .env
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://your-server.com")

if not VAPI_API_KEY or VAPI_API_KEY == "YOUR_VAPI_API_KEY":
    print("❌ Please set VAPI_API_KEY in your .env file first.")
    print("   Sign up at https://vapi.ai and get your API key.")
    exit(1)

# Load agent config
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'vapi_agent_config.json')
with open(config_path) as f:
    config = json.load(f)

# Replace BASE_URL placeholder in tool server URLs
config_str = json.dumps(config)
config_str = config_str.replace("{{BASE_URL}}", BASE_URL)
config = json.loads(config_str)

# Remove internal comment fields
for key in list(config.keys()):
    if key.startswith("_"):
        del config[key]

headers = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json"
}

print("Creating Napoli Pizzeria voice agent on Vapi.ai...")
print(f"Backend URL: {BASE_URL}")

# Check if assistant already exists
existing_id = os.getenv("VAPI_ASSISTANT_ID", "")
if existing_id:
    print(f"Updating existing assistant: {existing_id}")
    r = requests.patch(
        f"https://api.vapi.ai/assistant/{existing_id}",
        json=config,
        headers=headers
    )
else:
    print("Creating new assistant...")
    r = requests.post(
        "https://api.vapi.ai/assistant",
        json=config,
        headers=headers
    )

print(f"Status: {r.status_code}")
if r.status_code in (200, 201):
    data = r.json()
    assistant_id = data.get("id", "")
    print(f"\n✅ Assistant created/updated!")
    print(f"   ID: {assistant_id}")
    print(f"   Name: {data.get('name')}")
    print(f"\n   Add this to your .env:")
    print(f"   VAPI_ASSISTANT_ID={assistant_id}")
    
    # Now list phone numbers to link
    print("\n📞 Your Vapi phone numbers:")
    r2 = requests.get("https://api.vapi.ai/phone-number", headers=headers)
    if r2.status_code == 200:
        phones = r2.json()
        if phones:
            for p in phones:
                print(f"   - {p.get('number')} (ID: {p.get('id')})")
            print(f"\n   To link a phone number to this assistant, update VAPI_PHONE_NUMBER_ID in .env")
        else:
            print("   No phone numbers yet. Buy one at https://dashboard.vapi.ai/phone-numbers")
    
else:
    print(f"❌ Error: {r.text}")

print("\n📋 Next steps:")
print("1. Set VAPI_ASSISTANT_ID in your .env")
print("2. Buy a phone number at https://dashboard.vapi.ai/phone-numbers")
print("3. Link the phone number to this assistant in the Vapi dashboard")
print("4. Configure the Clover Hosted Checkout webhook URL in your Clover Merchant Dashboard:")
print(f"   Webhook URL: {BASE_URL}/webhook/payment")
print("5. Test by calling your Vapi phone number!")
