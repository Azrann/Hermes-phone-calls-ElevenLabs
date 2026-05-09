# Configuración — Referencia

Toda la configuración sensible vive en `~/.hermes/notifier.env` con permisos `0600`. Las funciones del skill leen este archivo automáticamente al importarse, sin necesidad de `python-dotenv`. Las variables de entorno tienen prioridad si están definidas.

## Variables requeridas

### ElevenLabs

| Variable                     | Descripción                                           |
|------------------------------|-------------------------------------------------------|
| `ELEVENLABS_API_KEY`         | API key con scope `convai_write`                      |
| `ELEVENLABS_PHONE_NUMBER_ID` | ID del número Twilio en ElevenLabs (`phnum_...`)      |

Para obtener el `phone_number_id`: `GET /v1/convai/phone-numbers`.

### Agentes ConvAI

Un agent_id por (caso de uso, idioma):

| Variable                   | Caso        | Idioma   |
|----------------------------|-------------|----------|
| `HERMES_AGENT_PERSONAL_EN` | Personal    | Inglés   |
| `HERMES_AGENT_PERSONAL_ES` | Personal    | Español  |
| `HERMES_AGENT_SOCIAL_EN`   | Social      | Inglés   |
| `HERMES_AGENT_SOCIAL_ES`   | Social      | Español  |
| `HERMES_AGENT_SERVICE_EN`  | Service     | Inglés   |
| `HERMES_AGENT_SERVICE_ES`  | Service     | Español  |

Si solo configuras un idioma para un caso, el script hace fallback al otro disponible.

### LLM y notificaciones

| Variable                              | Descripción                              |
|---------------------------------------|------------------------------------------|
| `OPENROUTER_API_KEY`                  | Para resúmenes con Llama 3 8B            |
| `TELEGRAM_BOT_TOKEN_NOTIFICATIONS`    | Bot que envía las notificaciones         |
| `TELEGRAM_CHAT_ID_NOTIFICATIONS`      | Chat al que se envían                    |

(También se aceptan `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` sin sufijo.)

### Opcionales

| Variable                | Default                       | Descripción                                |
|-------------------------|-------------------------------|--------------------------------------------|
| `DEFAULT_LANG`          | `es`                          | Idioma cuando no se puede detectar         |
| `HERMES_CONTACTS_PATH`  | `~/.hermes/contacts.json`     | Ruta alternativa para la agenda            |

## Plantilla completa

```
# ~/.hermes/notifier.env
# chmod 0600

ELEVENLABS_API_KEY=sk_...
ELEVENLABS_PHONE_NUMBER_ID=phnum_...

HERMES_AGENT_PERSONAL_EN=agent_...
HERMES_AGENT_PERSONAL_ES=agent_...
HERMES_AGENT_SOCIAL_EN=agent_...
HERMES_AGENT_SOCIAL_ES=agent_...
HERMES_AGENT_SERVICE_EN=agent_...
HERMES_AGENT_SERVICE_ES=agent_...

OPENROUTER_API_KEY=sk-or-...
TELEGRAM_BOT_TOKEN_NOTIFICATIONS=123456:ABC...
TELEGRAM_CHAT_ID_NOTIFICATIONS=123456789

DEFAULT_LANG=es
```

## Permisos y seguridad

```bash
mkdir -p ~/.hermes
chmod 0700 ~/.hermes
chmod 0600 ~/.hermes/notifier.env
chmod 0600 ~/.hermes/contacts.json
```

Ni `notifier.env` ni `contacts.json` deben subirse al repo. El `.gitignore` del proyecto los excluye, pero conviene verificar con `git check-ignore` antes de cualquier commit.
