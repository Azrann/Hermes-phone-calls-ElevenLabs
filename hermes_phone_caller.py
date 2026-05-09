"""
Hermes Phone Caller — ElevenLabs ConvAI Outbound Calls
=======================================================

3 casos de uso:
- personal: Llamar al usuario con un briefing
- social:   Llamar a un amigo/familiar con un recado
- service:  Llamar a un negocio para reservar/pedir servicio

Uso:
    from hermes_phone_caller import call_personal, call_social, call_service

El monitor se lanza automáticamente en background tras cada llamada
(call_monitor.py).

Configuración: ~/.hermes/notifier.env (ver notifier.env.example)
"""

import os
import subprocess
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config — lee de ~/.hermes/notifier.env (mismo patrón que el pipeline)
# ---------------------------------------------------------------------------
def _load_env_file(path: str) -> dict:
    """Carga un archivo .env en forma de dict."""
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


# Preferir variables de entorno, fallback a notifier.env
_env = _load_env_file(os.path.expanduser("~/.hermes/notifier.env"))


def _cfg(key: str, default: str = "") -> str:
    """Lee una clave de env vars o de notifier.env."""
    return os.environ.get(key) or _env.get(key, default)


ELEVENLABS_API_KEY = _cfg("ELEVENLABS_API_KEY")
OPENROUTER_API_KEY = _cfg("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = _cfg("TELEGRAM_BOT_TOKEN") or _cfg("TELEGRAM_BOT_TOKEN_NOTIFICATIONS")
TELEGRAM_CHAT_ID = _cfg("TELEGRAM_CHAT_ID") or _cfg("TELEGRAM_CHAT_ID_NOTIFICATIONS")

API_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound_call"

# Identificadores de Twilio/ElevenLabs — externalizados, NUNCA hardcodeados
PHONE_NUMBER_ID = _cfg("ELEVENLABS_PHONE_NUMBER_ID")


def _agent_id(use_case: str, lang: str) -> str:
    """Resuelve el agent_id desde la configuración."""
    key = f"HERMES_AGENT_{use_case.upper()}_{lang.upper()}"
    val = _cfg(key)
    if not val:
        # Fallback al idioma alterno si el solicitado no está configurado
        alt_lang = "en" if lang == "es" else "es"
        alt_key = f"HERMES_AGENT_{use_case.upper()}_{alt_lang.upper()}"
        val = _cfg(alt_key)
        if not val:
            raise RuntimeError(
                f"Missing agent config: set {key} (or {alt_key}) "
                f"in env vars or ~/.hermes/notifier.env"
            )
    return val


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _detect_language(text: str) -> str:
    """Detecta si el texto está en español o inglés."""
    text_lower = text.lower()

    es_words = {"hola", "buenos", "días", "tardes", "gracias", "por favor",
                "qué", "cómo", "cuál", "dónde", "cuándo", "quién", "estás",
                "tienes", "quieres", "sé", "más", "años", "noche", "mañana",
                "buenas", "vale", "venga", "hasta", "adiós", "saludos"}
    en_words = {"hello", "good morning", "good afternoon", "thanks", "please",
                "what", "how", "when", "where", "why", "are you", "do you",
                "have you", "your", "meeting", "flight", "schedule", "reminder",
                "call", "phone", "message", "booking", "reservation"}

    es_score = sum(1 for w in es_words if w in text_lower)
    en_score = sum(1 for w in en_words if w in text_lower)

    if en_score > es_score:
        return "en"
    if es_score > en_score:
        return "es"
    # Empate 0-0: default español (configurable via DEFAULT_LANG)
    return _cfg("DEFAULT_LANG", "es")


def _resolve_lang(use_case: str, lang_hint: str = None, text_sample: str = "") -> tuple:
    """Devuelve (agent_id, lang) resolviendo idioma e ID."""
    if use_case not in {"personal", "social", "service"}:
        raise ValueError(f"Unknown use_case: {use_case}")
    lang = lang_hint or _detect_language(text_sample)
    return _agent_id(use_case, lang), lang


def _call_api(agent_id: str, to_number: str, dynamic_variables: dict) -> dict:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not found in env or ~/.hermes/notifier.env")
    if not PHONE_NUMBER_ID:
        raise RuntimeError("ELEVENLABS_PHONE_NUMBER_ID not found in env or ~/.hermes/notifier.env")

    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "agent_id": agent_id,
        "agent_phone_number_id": PHONE_NUMBER_ID,
        "to_number": to_number,
        "conversation_initiation_client_data": {
            "dynamic_variables": dynamic_variables,
        },
    }
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _spawn_monitor(conv_id: str, agent_name: str, recipient: str, to_number: str,
                   call_objective: str, use_case: str, lang: str):
    """Lanza call_monitor.py en background (fire-and-forget).

    Loggea stdout/stderr a un archivo en ~/.hermes/call_logs para poder
    depurar fallos en lugar de tirarlo a /dev/null.
    """
    script = Path(__file__).with_name("call_monitor.py")
    if not script.exists():
        return  # Monitor no encontrado, skip silencioso

    log_dir = Path.home() / ".hermes" / "call_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"monitor_{conv_id[:16]}.log"

    cmd = [
        "python3", str(script),
        "--conversation-id", conv_id,
        "--agent-name", agent_name,
        "--recipient", recipient,
        "--to-number", to_number,
        "--objective", call_objective,
        "--use-case", use_case,
        "--lang", lang,
    ]

    # Fire-and-forget con logs persistentes
    logf = open(log_path, "ab")
    subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=logf,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def _extract_conv_id(api_result: dict) -> str:
    """Extrae el conversation_id del response, tolerando variantes de nombre."""
    return (
        api_result.get("conversation_id")
        or api_result.get("conversationId")
        or api_result.get("conversation", {}).get("id", "")
    )


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------
def call_personal(
    to_number: str,
    caller_name: str,
    briefing_content: str,
    objective: str = "",
    greeting: str = None,
    lang_hint: str = None,
) -> dict:
    agent_id, lang = _resolve_lang("personal", lang_hint, briefing_content)
    greeting = greeting or ("Good morning" if lang == "en" else "Hola")

    result = _call_api(agent_id, to_number, {
        "Greeting": greeting,
        "caller_name": caller_name,
        "briefing_content": briefing_content,
        "objective": objective or "",
    })

    if result.get("success"):
        conv_id = _extract_conv_id(result)
        if conv_id:
            _spawn_monitor(
                conv_id,
                agent_name="Asistente Personal",
                recipient=caller_name,
                to_number=to_number,
                call_objective=objective or "Briefing personal",
                use_case="personal",
                lang=lang,
            )
    return result


def call_social(
    to_number: str,
    recipient_name: str,
    caller_name: str,
    message: str,
    relationship: str = "a friend",
    objective: str = "",
    greeting: str = None,
    lang_hint: str = None,
) -> dict:
    agent_id, lang = _resolve_lang("social", lang_hint, message)
    greeting = greeting or ("Hi" if lang == "en" else "Hola")

    result = _call_api(agent_id, to_number, {
        "Greeting": greeting,
        "recipient_name": recipient_name,
        "caller_name": caller_name,
        "relationship": relationship,
        "message": message,
        "objective": objective or "",
    })

    if result.get("success"):
        conv_id = _extract_conv_id(result)
        if conv_id:
            _spawn_monitor(
                conv_id,
                agent_name="Mensajero Social",
                recipient=recipient_name,
                to_number=to_number,
                call_objective=objective or f"Recado de {caller_name}",
                use_case="social",
                lang=lang,
            )
    return result


def call_service(
    to_number: str,
    caller_name: str,
    caller_phone: str,
    business_type: str,
    request_type: str,
    desired_datetime: str,
    flexibility: str = "",
    special_requirements: str = "",
    caller_email: str = "",
    objective: str = "",
    greeting: str = None,
    lang_hint: str = None,
) -> dict:
    agent_id, lang = _resolve_lang("service", lang_hint, request_type)
    greeting = greeting or ("Good morning" if lang == "en" else "Buenos días")

    result = _call_api(agent_id, to_number, {
        "Greeting": greeting,
        "caller_name": caller_name,
        "caller_phone": caller_phone,
        "caller_email": caller_email or "",
        "business_type": business_type,
        "request_type": request_type,
        "desired_datetime": desired_datetime,
        "flexibility": flexibility or "",
        "special_requirements": special_requirements or "",
    })

    if result.get("success"):
        conv_id = _extract_conv_id(result)
        if conv_id:
            _spawn_monitor(
                conv_id,
                agent_name="Reservas y Servicios",
                recipient=f"{business_type} ({to_number})",
                to_number=to_number,
                call_objective=objective or request_type,
                use_case="service",
                lang=lang,
            )
    return result
