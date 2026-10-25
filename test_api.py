"""
test_api.py — one real API call to verify the key works.
Prints only the model reply. Never prints the key.
"""
import os, sys
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

key = os.environ.get("SARVAM_API_KEY", "").strip()
if not key:
    print("ERROR: SARVAM_API_KEY is empty in .env. Paste your key and retry.")
    sys.exit(1)

print("Key present: YES (not shown)")
print("Sending test request to sarvam-105b-conversations …\n")

client = SarvamAI(api_subscription_key=key)

response = client.chat.completions(
    messages=[{"role": "user", "content": "Reply with exactly: Sarvam API connected successfully."}],
    model="sarvam-105b-conversations",
)

reply = response.choices[0].message.content
print(f"Model reply: {reply}")
