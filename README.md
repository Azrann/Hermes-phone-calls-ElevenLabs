# Hermes Phone Calls (ElevenLabs)

Sistema de llamadas de voz outbound para Hermes usando ElevenLabs ConvAI + Twilio.

## Estructura

```
.
├── SKILL.md                    ← Documentación de skill Hermes (modo skill)
├── README.md                   ← Este archivo (repo independiente)
├── .gitignore
├── notifier.env.example        ← Plantilla de configuración
├── contacts.example.json       ← Ejemplo de agenda de contactos
├── scripts/
│   ├── caller.py               ← call_personal / call_social / call_service
│   ├── call_monitor.py         ← Polling + transcript + summary (auto-spawned)
│   └── contacts.py             ← resolve() / lookup() / list_all()
└── references/
    ├── api.md                  ← Endpoint y errores de ElevenLabs
    ├── config.md               ← Variables de notifier.env
    └── prompt-variables.md     ← Variables {{...}} dinámicas de los agentes
```

## Arquitectura

```
┌─────────────┐     outbound_call API      ┌──────────────┐
│  caller.py  │ ──────────────────────────→│  ElevenLabs  │
│  scripts/   │   + Twilio                 │   ConvAI     │
└─────────────┘                            │  (6 agents)  │
       │ spawn (fire-and-forget)           └──────────────┘
       ▼
┌─────────────┐     polling 15s            ┌──────────────┐
│call_monitor │ ──────────────────────────→│  ElevenLabs  │
│scripts/     │   ?include_transcript=true │ Conversations│
└─────────────┘                            └──────────────┘
       │
       │ LLM summary (meta-llama/llama-3-8b-instruct vía OpenRouter)
       ▼
┌─────────────┐
│   Telegram  │  ← Prefijo determinístico + evaluación LLM
└─────────────┘
```

## Configuración

1. Copia y rellena `~/.hermes/notifier.env`:

   ```bash
   mkdir -p ~/.hermes
   cp notifier.env.example ~/.hermes/notifier.env
   chmod 0600 ~/.hermes/notifier.env
   ```

2. Añade tu agenda de contactos:

   ```bash
   cp contacts.example.json ~/.hermes/contacts.json
   chmod 0600 ~/.hermes/contacts.json
   ```

3. Edita ambos archivos con tus credenciales y contactos.
   **Ningún ID, número o credencial debe vivir en el repo.**

## Agenda de contactos

El módulo `contacts.py` resuelve aliases como "llama a mamá", "dile a Elena" → contacto completo.

```python
from scripts.contacts import resolve
contact = resolve("mi mujer")
# → {"name": "Elena", "phone": "+44...", "relationship": "mi mujer", "lang": "es"}
```

Ver `contacts.example.json` para el formato completo.

## Uso

```python
from scripts.caller import call_personal, call_social, call_service
from scripts.contacts import resolve

# Briefing personal
result = call_personal(
    to_number="+44XXXXXXXXXX",
    caller_name="Alberto",
    briefing_content="Tu vuelo cambió de puerta...",
    objective="Avisar del cambio de puerta",
)

# Recado social (con contacto resuelto)
c = resolve("mi mujer")
result = call_social(
    to_number=c["phone"],
    recipient_name=c["name"],
    caller_name="Alberto",
    message="Llegaré tarde, no esperes para cenar",
    relationship=c.get("relationship", ""),
    lang_hint=c.get("lang"),
)

# Reserva en un negocio
result = call_service(
    to_number="+44XXXXXXXXXX",
    caller_name="Alberto Moreno",
    caller_phone="+44XXXXXXXXXX",
    business_type="restaurante",
    request_type="una mesa para 4",
    desired_datetime="viernes 21:00",
    special_requirements="trona para niño",
)
```

## Detección de idioma

Auto-detecta EN/ES desde el texto. Prioridad:
1. `lang_hint="en"` / `lang_hint="es"` (explícito)
2. `lang` del contacto resuelto desde `contacts.json`
3. Palabras clave del mensaje/briefing
4. `DEFAULT_LANG` en `notifier.env` (default: `es`)

## Monitor de llamadas

Tras cada llamada exitosa se lanza automáticamente `call_monitor.py` en background que:

1. Hace polling (cada 15s, hasta 15 min) hasta estado terminal (`done`, `completed`, `ended`, `failed`, `error`, `cancelled`).
2. Reintenta si el status es terminal pero el transcript aún no está indexado.
3. Extrae transcripción, normalizando roles `agent`/`user`/otros.
4. Resume con LLM evaluando éxito/fracaso, en el idioma de la llamada.
5. Envía a Telegram con prefijo **determinístico** (los datos reales nunca pasan por el LLM).
6. Guarda JSON en `~/.hermes/call_logs/` y logs del monitor en `~/.hermes/call_logs/monitor_<conv_id>.log`.

## API y referencias

Ver `references/`:
- `api.md` — Endpoints de ElevenLabs, errores HTTP
- `config.md` — Variables de `notifier.env`
- `prompt-variables.md` — Variables `{{...}}` para cada agente
