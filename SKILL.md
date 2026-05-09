---
name: elevenlabs-voice-caller
description: "ConvAI outbound calls via Twilio + ElevenLabs — Personal Assistant, Social Messenger, Service Booker. Resolves contacts by name/alias/relationship. Auto-detects EN/ES."
title: ElevenLabs Voice Caller
version: 2.0.0
author: Hermes
---

# ElevenLabs Voice Caller

Hace llamadas de voz salientes (outbound) usando 6 agentes preconfigurados en ElevenLabs ConvAI, conectados a un número Twilio. Cada función detecta automáticamente el idioma (inglés/español) y usa el agente correcto.

Incluye **agenda de contactos** para resolver "llama a mi madre", "dile a Elena", "phone John" → número de teléfono.

## Configuración

Toda la configuración sensible vive en `~/.hermes/notifier.env` (chmod 0600). Nunca hardcodear IDs ni números en el código.

Variables requeridas:

```
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_PHONE_NUMBER_ID=phnum_...
HERMES_AGENT_PERSONAL_EN=agent_...
HERMES_AGENT_PERSONAL_ES=agent_...
HERMES_AGENT_SOCIAL_EN=agent_...
HERMES_AGENT_SOCIAL_ES=agent_...
HERMES_AGENT_SERVICE_EN=agent_...
HERMES_AGENT_SERVICE_ES=agent_...
OPENROUTER_API_KEY=sk-or-...
TELEGRAM_BOT_TOKEN_NOTIFICATIONS=...
TELEGRAM_CHAT_ID_NOTIFICATIONS=...
DEFAULT_LANG=es
```

Ver `references/config.md` para detalles.

## Agentes (3 casos × 2 idiomas)

| Caso     | Variable EN                    | Variable ES                    |
|----------|--------------------------------|--------------------------------|
| Personal | `HERMES_AGENT_PERSONAL_EN`     | `HERMES_AGENT_PERSONAL_ES`     |
| Social   | `HERMES_AGENT_SOCIAL_EN`       | `HERMES_AGENT_SOCIAL_ES`       |
| Service  | `HERMES_AGENT_SERVICE_EN`      | `HERMES_AGENT_SERVICE_ES`      |

Voces típicas: Rachel M (EN, británico) / Raquel (ES, España). Modelo TTS: `eleven_flash_v2_5` para ES (requerido por ElevenLabs).

## Agenda de contactos

Vive en `~/.hermes/contacts.json` (ver `contacts.example.json`). Editas a mano. Formato:

```json
{
  "contacts": [
    {
      "id": "mother",
      "name": "Isabel",
      "phone": "+34XXXXXXXXX",
      "relationship": "mi madre",
      "lang": "es",
      "aliases": ["mamá", "mami", "madre", "ama"]
    }
  ]
}
```

### Modelo: `name` (saludo) vs `aliases` (búsqueda)

Esta es la distinción clave del sistema:

| Campo          | Para qué sirve                                                 | Participa en búsqueda |
|----------------|----------------------------------------------------------------|------------------------|
| `name`         | **Saludo** del agente en la llamada ("Hola Isabel")            | ❌ No                  |
| `aliases`      | Cómo el usuario invoca al contacto ("mamá", "mami", "madre")   | ✅ Sí                  |
| `id`           | Identificador único interno                                    | ✅ Sí                  |
| `relationship` | Tono de la llamada + búsqueda ("mi madre")                     | ✅ Sí                  |
| `phone`        | Número al que se llama                                         | ❌                     |
| `lang`         | Idioma preferido del agente para esta persona                  | ❌                     |

**El agente nunca dice "Hola mamá" — siempre dice "Hola Isabel"**, aunque el usuario haya dicho "llama a mami". Si quieres que un contacto se pueda buscar por su nombre real, añade el nombre **también** a `aliases` (es lo natural en amigos: `"name": "John", "aliases": ["John", "Johnny"]`).

### Política de resolución

| Caso                  | Comportamiento                                              |
|-----------------------|-------------------------------------------------------------|
| 1 match               | Devuelve el contacto                                        |
| 0 matches             | Lanza `ContactNotFound`                                     |
| 2+ matches            | Lanza `AmbiguousContact` con la lista de candidatos         |

**Importante:** ante ambigüedad, **falla**. Nunca llama al primer match silenciosamente. El LLM (yo) debe pedir aclaración al usuario.

### Qué entiende como entrada

Quita verbos/preámbulos automáticamente: `"llama a"`, `"llamar a"`, `"dile a"`, `"call"`, `"phone"`, `"tell"`, `"a"`, `"al"`, `"a la"`. Y normaliza acentos/mayúsculas. Por tanto todas estas formas funcionan igual sobre el ejemplo de Isabel:

- `"llama a mamá"` → matchea alias `"mamá"`
- `"Llama a mami"` → matchea alias `"mami"`
- `"dile a madre"` → matchea alias `"madre"`
- `"mi madre"` → matchea `relationship`
- En todos los casos: `name="Isabel"` se pasa al saludo del agente.

## Cómo usar desde Hermes

El LLM (yo) invoca las funciones de `scripts/caller.py` usando `execute_code` o `terminal`. La API key y el resto de config se leen automáticamente de `~/.hermes/notifier.env`.

### Flujo recomendado: contacto + llamada

```python
from scripts import contacts
from scripts.caller import call_social

# 1. Resolver el contacto. Si falla, pedir aclaración al usuario.
try:
    contact = contacts.resolve("dile a mamá")
    # contact = {
    #   "name": "Isabel",          ← el agente saluda con esto
    #   "phone": "+34XXX...",
    #   "relationship": "mi madre",
    #   "lang": "es",
    #   "aliases": [...],
    # }
except contacts.AmbiguousContact as e:
    # e.matches es la lista de candidatos: pedir al usuario que elija
    ...
except contacts.ContactNotFound:
    # No hay alias que matchee — pedir al usuario que añada el contacto
    ...

# 2. Hacer la llamada. recipient_name = contact["name"] (Isabel),
#    NO el query original ("mamá"). El agente dirá "Hola Isabel".
result = call_social(
    to_number=contact["phone"],
    recipient_name=contact["name"],
    caller_name="Alberto",
    message="Llegaré tarde, no esperes para cenar",
    relationship=contact.get("relationship", ""),
    lang_hint=contact.get("lang"),  # respeta el idioma del contacto
)
```

### Ejemplos por caso de uso

**1. Briefing personal (te llama a ti mismo)**

```python
from scripts.caller import call_personal

result = call_personal(
    to_number="+44XXXXXXXXXX",       # tu propio número, o resuelto desde contacts
    caller_name="Alberto",
    briefing_content="Tu vuelo a Málaga ha cambiado de puerta. Ahora B12, embarque 14:30.",
    objective="Avisar del cambio de puerta",
)
# → {"success": true, "conversation_id": "conv_xxx", "callSid": "CAxxx"}
```

**2. Recado social (resuelto desde contacts)**

```python
from scripts import contacts
from scripts.caller import call_social

c = contacts.resolve("mi mujer")
result = call_social(
    to_number=c["phone"],
    recipient_name=c["name"],
    caller_name="Alberto",
    message="Llegaré tarde hoy, la reunión se ha alargado.",
    relationship=c.get("relationship", "su pareja"),
    lang_hint=c.get("lang"),
)
```

**3. Reservar mesa**

```python
from scripts.caller import call_service

result = call_service(
    to_number="+442081234567",
    caller_name="Alberto Moreno",
    caller_phone="+44XXXXXXXXXX",
    business_type="restaurante",
    request_type="una mesa para 4",
    desired_datetime="viernes 21:00",
    flexibility="cualquier noche este fin de semana",
    special_requirements="trona para niño",
)
```

## Variables dinámicas por agente

Ver `references/prompt-variables.md` para la tabla completa con ejemplos EN/ES.

| Agente              | Variables                                                                                              |
|---------------------|---------------------------------------------------------------------------------------------------------|
| Personal            | `Greeting`, `caller_name`, `briefing_content`, `objective`                                              |
| Social              | `Greeting`, `recipient_name`, `caller_name`, `relationship`, `message`, `objective`                     |
| Service             | `Greeting`, `caller_name`, `caller_phone`, `caller_email`, `business_type`, `request_type`, `desired_datetime`, `flexibility`, `special_requirements` |

## Detección de idioma

Tres niveles de prioridad, de más a menos específico:

1. `lang_hint="en"` / `lang_hint="es"` — fuerza explícitamente.
2. `lang` del contacto resuelto desde `contacts.json`.
3. Auto-detección por palabras clave en el texto del mensaje/briefing.
4. `DEFAULT_LANG` en `notifier.env` cuando no hay señal (default: `es`).

## Monitor de llamadas

**Se lanza solo.** Tras cada llamada exitosa, `caller.py` spawnea `call_monitor.py` en background automáticamente. No hay que invocarlo a mano.

Lo que hace:

1. Polling cada 15s (hasta 15 min) hasta que la llamada está en estado terminal.
2. Estados terminales reconocidos: `done`, `completed`, `failed`, `ended`, `error`, `cancelled`. Cualquier otro estado (`initiated`, `in-progress`, etc.) cuenta como "aún en curso" — esto es importante: el monitor antiguo tenía un bug por el que devolvía resultados inmediatos cuando ElevenLabs respondía con `initiated` en el primer poll.
3. Si el status es terminal pero el transcript está vacío, reintenta hasta 3 veces (a veces ElevenLabs marca `done` antes de indexar el transcript).
4. Extrae transcript vía `/v1/convai/conversations/{id}?include_transcript=true`, normalizando roles `agent`/`user`/otros.
5. Resume con LLM (Llama 3 8B vía OpenRouter) en el idioma de la llamada.
6. Envía a Telegram con **prefijo determinístico** construido en Python puro (los datos reales — duración, coste, status, destinatario — nunca pasan por el LLM, evita alucinaciones).
7. Guarda JSON estructurado en `~/.hermes/call_logs/{conv_id}.json`.

Logs del propio monitor (para depurar fallos del subproceso): `~/.hermes/call_logs/monitor_{conv_id}.log`.

## Errores habituales

| Código  | Origen      | Significado                                    | Fix                                                  |
|---------|-------------|------------------------------------------------|------------------------------------------------------|
| —       | `contacts`  | `ContactNotFound`                              | Añadir el contacto a `~/.hermes/contacts.json`       |
| —       | `contacts`  | `AmbiguousContact`                             | Pedir al usuario que use nombre completo o alias     |
| 401     | ElevenLabs  | `missing_permissions` (`convai_write`)         | Revisar scope en ElevenLabs dashboard                |
| 400     | ElevenLabs  | `voice_not_found`                              | Añadir voz en ElevenLabs UI                          |
| 400     | ElevenLabs  | "Non-english must use turbo/flash v2_5"        | El agente ES debe usar `eleven_flash_v2_5`           |
| 404     | ElevenLabs  | `document_not_found` (phone_number)            | Verificar `ELEVENLABS_PHONE_NUMBER_ID`               |
| 403     | ElevenLabs  | Número no aprobado para outbound               | Verificar Twilio + ElevenLabs compliance             |

## Ficheros del skill

```
elevenlabs-voice-caller/
├── SKILL.md
├── contacts.example.json
├── references/
│   ├── api.md                   ← Endpoint /v1/convai/twilio/outbound_call, errores
│   ├── prompt-variables.md      ← Variables {{...}} de cada agente
│   └── config.md                ← Variables de notifier.env
└── scripts/
    ├── caller.py                ← call_personal / call_social / call_service
    ├── call_monitor.py          ← Polling + transcript + summary (auto-spawned)
    └── contacts.py              ← resolve() / lookup() / list_all()
```

## Notas técnicas

- **Twilio outbound requiere que el número `from` esté verificado** para evitar abuso.
- Las funciones leen `~/.hermes/notifier.env` automáticamente, sin necesidad de `python-dotenv`.
- `conversation_initiation_client_data.dynamic_variables` permite inyectar texto en tiempo real en el agente.
- El monitor se autolanza con `subprocess.Popen(start_new_session=True)`. Sobrevive a que el proceso padre termine.
