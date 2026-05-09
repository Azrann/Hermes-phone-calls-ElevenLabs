"""
Call Monitor — ElevenLabs ConvAI
=================================

Proceso hijo fire-and-forget que:
1. Hace polling a la API de ElevenLabs hasta que la llamada termina
2. Extrae la transcripción
3. Resume con LLM (vía OpenRouter) evaluando éxito/fracaso
4. Envía a Telegram con prefijo determinístico (datos reales nunca pasan por el LLM)
5. Guarda JSON local en ~/.hermes/call_logs/

Lanzado automáticamente por hermes_phone_caller.py tras cada llamada.
"""

import argparse
import json
import os
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ELEVENLABS_API = "https://api.elevenlabs.io/v1/convai/conversations"
LLM_MODEL = "meta-llama/llama-3-8b-instruct"

# Estados terminales de ElevenLabs ConvAI.
# Lista BLANCA (no negra): cualquier estado desconocido cuenta como "no terminado".
# ElevenLabs devuelve "initiated"/"in-progress" durante la llamada y
# "done"/"failed" al terminar. Normalizamos guiones a underscores por seguridad.
TERMINAL_STATUSES = {"done", "completed", "failed", "ended", "error", "cancelled"}


def _load_env(path: str) -> dict:
    result = {}
    p = Path(path)
    if not p.exists():
        return result
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


_env = _load_env(os.path.expanduser("~/.hermes/notifier.env"))


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key) or _env.get(key, default)


ELEVENLABS_KEY = _cfg("ELEVENLABS_API_KEY")
OPENROUTER_KEY = _cfg("OPENROUTER_API_KEY")
TELEGRAM_BOT = _cfg("TELEGRAM_BOT_TOKEN") or _cfg("TELEGRAM_BOT_TOKEN_NOTIFICATIONS")
TELEGRAM_CHAT = _cfg("TELEGRAM_CHAT_ID") or _cfg("TELEGRAM_CHAT_ID_NOTIFICATIONS")


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# ElevenLabs API
# ---------------------------------------------------------------------------
def fetch_conversation(conv_id: str) -> dict:
    headers = {"xi-api-key": ELEVENLABS_KEY}
    url = f"{ELEVENLABS_API}/{conv_id}?include_transcript=true"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def is_finished(status: str) -> bool:
    """True solo para estados terminales conocidos.

    Lista blanca: cualquier estado nuevo o desconocido (ej: 'initiated',
    'in-progress', 'in_progress', 'processing', 'queued') cuenta como
    'aún no terminada' hasta que sepamos que sí lo está.
    """
    if not status:
        return False
    norm = status.lower().replace("-", "_")
    return norm in TERMINAL_STATUSES


def _turn_role(turn: dict) -> str:
    """Normaliza el rol del turno. ElevenLabs usa 'role' o 'speaker'
    con valores como 'agent'/'user'/'assistant'/'human'."""
    raw = (turn.get("role") or turn.get("speaker") or "").lower()
    if raw in ("agent", "assistant", "ai", "bot"):
        return "agent"
    if raw in ("user", "human", "caller", "callee"):
        return "user"
    return "other"


def extract_dialogue(transcript: list) -> str:
    lines = []
    for turn in transcript:
        msg = (turn.get("message") or "").strip()
        if not msg:
            continue
        t = turn.get("time_in_call_secs", 0)
        role = _turn_role(turn)
        if role == "agent":
            label = "🤖 Agente"
        elif role == "user":
            label = "👤 Persona"
        else:
            label = "ℹ️ Sistema"
        lines.append(f"[{t}s] {label}: {msg}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM Summary — prefijo determinístico + resumen LLM
# ---------------------------------------------------------------------------
def llm_summarize(dialogue: str, use_case: str, objective: str, lang: str = "es") -> str:
    """El LLM evalúa el éxito de la llamada. Prompt e idioma de salida
    se eligen según el idioma de la conversación."""
    if not OPENROUTER_KEY:
        return "⚠️ SIN LLM — no hay OPENROUTER_API_KEY"

    if lang == "en":
        use_case_desc = {
            "personal": "Personal Assistant (calling the user with a briefing)",
            "social": "Social Messenger (calling a friend/family with a message)",
            "service": "Bookings & Services (calling a business to book/request a service)",
        }.get(use_case, "Voice call")

        system_msg = (
            "You are a concise voice-call evaluator. Always reply in English, "
            "in a single line, max 200 characters."
        )
        prompt = f"""You are a voice-call evaluator. Analyze this transcript and reply in ONE LINE (max 200 chars).

Call type: {use_case_desc}
Expected objective: {objective}

Evaluate:
1. Was the objective achieved? (yes/no/partial)
2. Were there any technical or communication issues?
3. Did the recipient accept the information or cooperate?

Reply only with the concise evaluation, no preamble.

Transcript:
{dialogue}

Evaluation:"""
    else:
        use_case_desc = {
            "personal": "Asistente Personal (llamada al propio usuario para dar un briefing)",
            "social": "Mensajero Social (llamada a un amigo/familiar para dar un recado)",
            "service": "Reservas y Servicios (llamada a un negocio para reservar o pedir servicio)",
        }.get(use_case, "Llamada de voz")

        system_msg = (
            "Eres un evaluador conciso de llamadas telefónicas. Responde siempre "
            "en español, en una sola línea, máximo 200 caracteres."
        )
        prompt = f"""Eres un evaluador de llamadas de voz. Analiza esta transcripción y responde en UNA SOLA LÍNEA (máximo 200 caracteres).

Tipo de llamada: {use_case_desc}
Objetivo esperado: {objective}

Evalúa:
1. ¿Se consiguió el objetivo? (sí/no/parcial)
2. ¿Hubo algún problema técnico o de comunicación?
3. ¿El destinatario aceptó la información o cooperó?

Responde solo con la evaluación concisa, sin introducción.

Transcripción:
{dialogue}

Evaluación:"""

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 200,
                "temperature": 0.3,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ Error LLM: {str(e)[:80]}"


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def send_telegram(text: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        log("⚠️ No Telegram config, skipping notification")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        log("✅ Telegram sent")
    except Exception as e:
        log(f"❌ Telegram error: {e}")


# ---------------------------------------------------------------------------
# Prefijo determinístico (nunca pasa por el LLM)
# ---------------------------------------------------------------------------
def build_prefix(use_case: str, agent_name: str, recipient: str,
                 objective: str, status: str, duration: int, cost: int) -> str:
    emoji = {
        "personal": "📢",
        "social": "💬",
        "service": "📞",
    }.get(use_case, "📞")

    case_label = {
        "personal": "Asistente Personal",
        "social": "Mensajero Social",
        "service": "Reservas",
    }.get(use_case, agent_name)

    status_emoji = "✅" if status.lower() in ("done", "completed", "ended") else "⚠️"
    cost_str = f"{cost/1000:.2f}¢" if cost else "N/A"

    return (
        f"{emoji} <b>{case_label}</b> → {recipient}\n"
        f"Objetivo: <i>{objective}</i>\n"
        f"{status_emoji} Estado: {status} | {duration}s | {cost_str}\n"
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def monitor(conv_id: str, agent_name: str, recipient: str, to_number: str,
            objective: str, use_case: str, lang: str = "es",
            poll_interval: int = 15, max_minutes: int = 15):
    log(f"Monitoring {conv_id[:20]}... → {to_number} (lang={lang})")

    deadline = time.time() + max_minutes * 60
    attempt = 0
    empty_transcript_retries = 0
    MAX_EMPTY_RETRIES = 3  # Si status=terminal pero transcript vacío, reintenta

    while time.time() < deadline:
        attempt += 1
        try:
            data = fetch_conversation(conv_id)
            status = data.get("status", "unknown")
            meta = data.get("metadata", {})
            duration = meta.get("call_duration_secs", 0)
            cost = meta.get("cost", 0)

            log(f" Attempt {attempt} — status={status} duration={duration}s cost={cost}")

            if is_finished(status):
                transcript = data.get("transcript", []) or []

                # Defensa: a veces el status pasa a 'done' antes de que
                # el transcript esté indexado. Reintenta unas veces.
                if not transcript and empty_transcript_retries < MAX_EMPTY_RETRIES:
                    empty_transcript_retries += 1
                    log(f" Status terminal pero transcript vacío, "
                        f"reintento {empty_transcript_retries}/{MAX_EMPTY_RETRIES}")
                    time.sleep(poll_interval)
                    continue

                log("Call finished, processing...")

                if not transcript:
                    prefix = build_prefix(use_case, agent_name, recipient,
                                          objective, status, duration, cost)
                    send_telegram(f"{prefix}\n<i>Transcript vacío</i>")
                    return

                dialogue = extract_dialogue(transcript)
                summary = llm_summarize(dialogue, use_case, objective, lang)
                prefix = build_prefix(use_case, agent_name, recipient,
                                      objective, status, duration, cost)

                msg = (
                    f"{prefix}\n<b>Evaluación:</b> <i>{summary}</i>\n\n"
                    f"<code>{dialogue[:900]}</code>"
                )
                send_telegram(msg)

                # Guardar JSON local
                out_dir = Path.home() / ".hermes" / "call_logs"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{conv_id}.json"
                out_path.write_text(json.dumps({
                    "conversation_id": conv_id,
                    "use_case": use_case,
                    "lang": lang,
                    "agent_name": agent_name,
                    "recipient": recipient,
                    "to_number": to_number,
                    "objective": objective,
                    "status": status,
                    "duration_secs": duration,
                    "cost": cost,
                    "evaluation": summary,
                    "dialogue": dialogue,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                log(f"Saved to {out_path}")
                return

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                log(" 404 — conversation not yet available, retrying...")
            else:
                log(f" HTTP error: {e}")
        except Exception as e:
            log(f" Error: {e}")

        time.sleep(poll_interval)

    log("⏱️ Timeout — call did not finish in time")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--agent-name", default="Agente")
    parser.add_argument("--recipient", default="Usuario")
    parser.add_argument("--to-number", default="")
    parser.add_argument("--objective", default="")
    parser.add_argument("--use-case", default="personal",
                        choices=["personal", "social", "service"])
    parser.add_argument("--lang", default="es", choices=["es", "en"])
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--max-minutes", type=int, default=15)
    args = parser.parse_args()

    monitor(
        args.conversation_id,
        args.agent_name,
        args.recipient,
        args.to_number,
        args.objective,
        args.use_case,
        args.lang,
        args.poll_interval,
        args.max_minutes,
    )


if __name__ == "__main__":
    main()
