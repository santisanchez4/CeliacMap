"""Replay named-place searches against production; only normal chat usage/logs.

Run: python db/checks/chat_named_live.py
Uses the frontend public anon key. Never submits contributions.
"""
import json
import re
import urllib.request
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[2]
config = (root / "js/config.js").read_text(encoding="utf-8")
base = re.search(r'SUPABASE_URL: "([^"]+)', config)[1]
key = re.search(r'SUPABASE_ANON_KEY:\s*"([^"]+)', config)[1]
history = []
session = "celiac-test-named-" + uuid4().hex
results = []
for message, expected in [
    ("los leños en montevideo, pasame informacion", ["Los Leños"]),
    ("y dalebertt y Cafe Ramona tambien en montevideo?", ["Dalbertt", "Café Ramona - Centro"]),
    ("estoy viendo dalbertt en el Mapa, en montevideo con la direccion Mercedes 799, 11000 Montevideo, Departamento de Montevideo, Uruguay", ["Dalbertt"]),
    ("puedes pasarme info de ese restaurante? asi como el de los Leños?", ["Dalbertt", "Los Leños"]),
]:
    history.append({"role": "user", "content": message})
    body = {"messages": history, "session_token": session, "pending_submission": None}
    request = urllib.request.Request(base + "/functions/v1/chat", data=json.dumps(body).encode(), headers={
        "apikey": key, "Authorization": "Bearer " + key,
        "Content-Type": "application/json", "Origin": "https://celiacmap.org",
    })
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.load(response)
    names = [p["name"] for p in data.get("places", [])]
    result = {"message": message, "reply": data.get("reply"), "places": names,
              "passed": all(name in names for name in expected) and not data.get("action") and not data.get("pending_submission")}
    results.append(result)
    print(json.dumps(result, ensure_ascii=True), flush=True)
    history.append({"role": "assistant", "content": data["reply"]})
assert all(r["passed"] for r in results), "Named-place replay failed; inspect replies above"
