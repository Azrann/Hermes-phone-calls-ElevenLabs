# Hermes Phone Calls (ElevenLabs)

Sistema de llamadas de voz outbound para Hermes usando ElevenLabs ConvAI + Twilio.

## Arquitectura

```
┌─────────────┐     outbound_call API      ┌──────────────┐
│  hermes     │ ──────────────────────────→│  ElevenLabs  │
│  phone      │   + Twilio                 │   ConvAI     │
│  caller     │                            │  (6 agents)  │
└─────────────┘                            └──────────────┘
       │
       │ spawnea (fire-and-forget)
       ▼
┌─────────────┐     polling 15s            ┌──────────────┐
│  call       │ ──────────────────────────→│  ElevenLabs  │
│  monitor    │   ?include_transcript=true │ Conversations│
│ (background)│                            └──────────────┘
└─────────────┘
       │
       │ LLM summary (meta-llama/llama-3-8b-instruct)
       ▼
┌─────────────┐
│   Telegram  │  ← Prefijo determinístico + evaluación LLM
└─────────────┘
```

## Configuración

1. Copia `notifier.env.example` a `~/.hermes/notifier.env` y rellena los valores:

   ```bash
   mkdir -p ~/.hermes
   cp notifier.env.example ~/.hermes/notifier.env
   chmod 0600 ~/.hermes/notifier.env
   ```

2. Edita el archivo con tus credenciales:
   - `ELEVENLABS_API_KEY` — API key de ElevenLabs
   - `ELEVENLABS_PHONE_NUMBER_ID` — ID del número Twilio en ElevenLabs
   - `HERMES_AGENT_<USE_CASE>_<LANG>` — un agent_id por (caso, idioma)
   - `OPENROUTER_API_KEY` — para los resúmenes LLM
   - `TELEGRAM_BOT_TOKEN_NOTIFICATIONS` y `TELEGRAM_CHAT_ID_NOTIFICATIONS`

   Ningún ID de agente, número de teléfono o credencial debe vivir en el repo.

## Casos de uso (agentes)

| Caso     | Variables de entorno requeridas                  | Descripción                                              |
| -------- | ------------------------------------------------ | -------------------------------------------------------- |
| Personal | `HERMES_AGENT_PERSONAL_EN` / `_ES`               | Llamada al usuario con un briefing                       |
| Social   | `HERMES_AGENT_SOCIAL_EN` / `_ES`                 | Llamada a un amigo/familiar con un recado                |
| Service  | `HERMES_AGENT_SERVICE_EN` / `_ES`                | Llamada a un negocio para reservar/pedir servicio        |

## Uso

```python
from hermes_phone_caller import call_personal, call_social, call_service

# Briefing personal
result = call_personal(
    to_number="+44XXXXXXXXXX",
    caller_name="Alice",
    briefing_content="Tu vuelo cambió de puerta...",
    objective="Avisar del cambio de puerta",
)

# Recado social
result = call_social(
    to_number="+44XXXXXXXXXX",
    recipient_name="Bob",
    caller_name="Alice",
    message="Llegaré tarde, no esperes para cenar",
    relationship="su pareja",
)

# Reserva en un negocio
result = call_service(
    to_number="+44XXXXXXXXXX",
    caller_name="Alice Smith",
    caller_phone="+44XXXXXXXXXX",
    business_type="restaurante",
    request_type="una mesa para 4",
    desired_datetime="viernes 21:00",
    special_requirements="trona para niño",
)
```

## Detección de idioma

Auto-detecta EN/ES analizando el texto del mensaje/briefing. Se puede forzar con `lang_hint="en"` / `lang_hint="es"`. El default cuando no hay señal es configurable vía `DEFAULT_LANG` en `notifier.env`.

## Monitor de llamadas

Tras cada llamada exitosa, se lanza automáticamente `call_monitor.py` en background que:

1. Hace polling (cada 15s, hasta 15 min) hasta que la llamada está en estado terminal (`done`, `completed`, `ended`, `failed`, `error`, `cancelled`).
2. Reintenta unas veces si el status es terminal pero el transcript aún no está indexado.
3. Extrae la transcripción completa, normalizando los roles (`agent`/`user`/otros).
4. Resume con LLM evaluando éxito/fracaso, en el mismo idioma de la llamada.
5. Envía a Telegram con prefijo **determinístico** en Python puro (los datos reales nunca pasan por el LLM).
6. Guarda JSON en `~/.hermes/call_logs/` y los logs del propio monitor en `~/.hermes/call_logs/monitor_<conv_id>.log`.

## Scripts

| Archivo                   | Propósito                                     |
| ------------------------- | --------------------------------------------- |
| `hermes_phone_caller.py`  | Rutina de llamadas (3 funciones públicas)     |
| `call_monitor.py`         | Polling + transcript + summary + notificación |
| `notifier.env.example`    | Plantilla de configuración                    |
