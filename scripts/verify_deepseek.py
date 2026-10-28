"""Verify deployed RAG generation without printing credentials."""
import argparse
import json
import sys
import time
from pathlib import Path
import httpx
from dotenv import dotenv_values

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://127.0.0.1:8080")
p.add_argument("--question", default="How do I reset my password?")
p.add_argument("--output", type=Path, default=Path("evaluation/results/deepseek-live.json"))
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
env = dotenv_values(root / ".env")
secret = (env.get("DEEPSEEK_API_KEY") or "").strip()
if not secret:
    raise SystemExit("No key found. Set DEEPSEEK_API_KEY in the local .env file and save it.")
result = {"question": args.question, "configured_model": env.get("DEEPSEEK_MODEL", "deepseek-flash"),
          "provider_generation_verified": False, "answer": "", "sources": [], "events": []}
start = time.perf_counter()
try:
    with httpx.Client(timeout=180) as client:
        health = client.get(args.url + "/api/health")
        health.raise_for_status()
        result["health"] = health.json()
        if not result["health"].get("generation_configured"):
            raise RuntimeError("Restart the API container to load the saved key.")
        with client.stream("POST", args.url + "/api/chat", json={"question": args.question, "history": []}) as response:
            response.raise_for_status()
            event = "message"
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    result["events"].append(event)
                    if event == "sources":
                        result["search_query"] = data["query"]
                        result["sources"] = [{k: hit.get(k) for k in ("source", "heading", "citation", "score")} for hit in data["items"]]
                    elif event == "replace":
                        result["answer"] = data["text"]
                    elif event == "token":
                        result["answer"] += data["text"]
                        result.setdefault("first_token_arrival_ms", round((time.perf_counter()-start)*1000))
                        result["token_frames"] = result.get("token_frames", 0) + 1
                    elif event == "done":
                        result["completion"] = data
                        result["done_arrival_ms"] = round((time.perf_counter()-start)*1000)
                    elif event == "error":
                        result["error"] = data.get("message", "Provider request failed.")
    done = result.get("completion", {})
    result["provider_generation_verified"] = bool(done.get("intent") == "answer" and done.get("generation_usage", {}).get("output_tokens", 0) > 0 and result["answer"])
    if not result["provider_generation_verified"]:
        result.setdefault("error", "A grounded provider answer with token usage was not returned. Check the recorded intent and provider configuration.")
except Exception as exc:
    # Do not include exception text: HTTP exceptions can carry sensitive data.
    result["error"] = "Verification failed (" + type(exc).__name__ + "). Check local service availability and provider configuration."
result["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
args.output.parent.mkdir(parents=True, exist_ok=True)
serialized = json.dumps(result, ensure_ascii=False, indent=2).replace(secret, "[REDACTED]")
args.output.write_text(serialized)
print(json.dumps({"provider_generation_verified": result["provider_generation_verified"], "intent": result.get("completion", {}).get("intent"), "elapsed_ms": result["elapsed_ms"], "output": str(args.output), "error": result.get("error")}, ensure_ascii=False))
sys.exit(0 if result["provider_generation_verified"] else 1)
