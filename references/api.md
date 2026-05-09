# ElevenLabs ConvAI API — Referencia Técnica

Documentado tras trabajo real con la API.

## Outbound Call

`POST /v1/convai/twilio/outbound_call`

Headers:

```
xi-api-key: sk_...
Content-Type: application/json
```

Body mínimo:

```json
{
  "agent_id": "agent_xxxx",
  "agent_phone_number_id": "phnum_xxxx",
  "to_number": "+44...",
  "conversation_initiation_client_data": {}
}
```

Con dynamic variables:

```json
{
  "agent_id": "agent_xxxx",
  "agent_phone_number_id": "phnum_xxxx",
  "to_number": "+44...",
  "conversation_initiation_client_data": {
    "dynamic_variables": {
      "caller_name": "...",
      "briefing_content": "...",
      "Greeting": "Hola"
    }
  }
}
```

### Respuesta

```json
{
  "success": true,
  "message": "Success",
  "conversation_id": "conv_xxxx",
  "callSid": "CAxxxx"
}
```

El campo principal es `conversation_id`. En algunas versiones de la API también se ha visto `conversationId` (camelCase). El módulo `caller.py` tolera ambos.

## Obtener Conversación + Transcript

`GET /v1/convai/conversations/{conv_id}?include_transcript=true`

`include_transcript=true` es **obligatorio** para obtener el campo `transcript`.

### Estados (`status`)

Durante la llamada el status pasa por:

- `initiated` — la llamada se ha encolado, aún no contestada
- `in-progress` (a veces `in_progress`) — llamada activa
- `done` / `completed` / `ended` — terminada con éxito
- `failed` / `error` / `cancelled` — terminada con fallo

**No asumas que un estado desconocido implica "terminada".** El monitor usa una lista blanca de estados terminales precisamente para evitar el bug de procesar llamadas que aún no han empezado.

### Transcript format

```json
{
  "status": "done",
  "metadata": {
    "call_duration_secs": 87,
    "cost": 1240
  },
  "transcript": [
    {
      "role": "agent",
      "message": "...",
      "time_in_call_secs": 0,
      "source_medium": "audio"
    },
    {
      "role": "user",
      "message": "...",
      "time_in_call_secs": 4
    }
  ]
}
```

El campo de rol puede llegar como `role` o `speaker` según versión. Valores observados: `agent`, `assistant`, `ai`, `user`, `human`, `caller`. El módulo `call_monitor.py` los normaliza.

A veces el `status` pasa a `done` antes de que el array `transcript` esté indexado — el monitor reintenta hasta 3 veces en este caso.

## Listar Phone Numbers

`GET /v1/convai/phone-numbers`

Útil para obtener el `phone_number_id` que va en `ELEVENLABS_PHONE_NUMBER_ID`.

## Listar Agentes

`GET /v1/convai/agents`

## Crear Agente

`POST /v1/convai/agents/create`

```json
{
  "name": "Agent Name",
  "conversation_config": {
    "agent": {
      "prompt": {"prompt": "..."},
      "first_message": "Hola...",
      "language": "es"
    },
    "tts": {
      "voice_id": "...",
      "model_id": "eleven_flash_v2_5"
    }
  }
}
```

## Errores

| HTTP | Código                | Significado                              | Fix                                                       |
|------|-----------------------|------------------------------------------|-----------------------------------------------------------|
| 401  | `missing_permissions` | Falta `convai_write`                     | Dashboard → API Keys → ElevenAgents → Write               |
| 400  | `voice_not_found`     | Voz no existe en cuenta                  | Añadir voz en dashboard                                   |
| 400  | `invalid_parameters`  | "Non-english must use turbo/flash v2_5"  | Usar `eleven_flash_v2_5` para ES                          |
| 404  | `document_not_found`  | `phone_number_id` equivocado             | Verificar en `/v1/convai/phone-numbers`                   |
| 403  | —                     | Número no aprobado para outbound         | Verificar Twilio + ElevenLabs compliance                  |
