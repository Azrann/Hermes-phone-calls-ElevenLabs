# Agent Prompt Dynamic Variables Reference

Reference for the `{{variable}}` placeholders used in the ElevenLabs agent prompts. These must match exactly when passed in `conversation_initiation_client_data.dynamic_variables`.

## Personal Assistant (EN + ES)

| Variable           | Ejemplo EN                            | Ejemplo ES                              | Uso                                       |
|--------------------|---------------------------------------|------------------------------------------|-------------------------------------------|
| `Greeting`         | "Good morning"                        | "Hola"                                   | Primer saludo                             |
| `caller_name`      | "Alice"                               | "Alice"                                  | Nombre del destinatario (el usuario)      |
| `briefing_content` | "Your flight has changed gates..."    | "Tu vuelo ha cambiado de puerta..."      | Info principal a comunicar                |
| `objective`        | "Alert about gate change"             | "Avisar del cambio de puerta"            | Propósito de la llamada                   |

**Primer mensaje (ES):** `{{Greeting}}, soy tu asistente. Cuando quieras empezamos.`
**Primer mensaje (EN):** `{{Greeting}}, it's your assistant. Ready when you are.`

---

## Social Messenger (EN + ES)

| Variable          | Ejemplo EN                            | Ejemplo ES                          | Uso                                  |
|-------------------|---------------------------------------|--------------------------------------|--------------------------------------|
| `Greeting`        | "Hi"                                  | "Hola"                               | Primer saludo                        |
| `recipient_name`  | "Bob"                                 | "Bob"                                | A quién se llama                     |
| `caller_name`     | "Alice"                               | "Alice"                              | De parte de quién                    |
| `relationship`    | "his wife"                            | "su pareja"                          | Relación (afecta el tono)            |
| `message`         | "I'll be late tonight..."             | "Llegaré tarde..."                   | El recado real                       |
| `objective`       | "Let her know I'm late"               | "Avisar de que llego tarde"          | Qué busca la llamada                 |

**Primer mensaje (ES):** `{{Greeting}} {{recipient_name}}, soy un asistente que llama de parte de {{caller_name}}, ¿tienes un momento?`
**Primer mensaje (EN):** `{{Greeting}} {{recipient_name}}, this is an assistant calling on behalf of {{caller_name}} — got a quick second?`

---

## Service Booker (EN + ES)

| Variable               | Ejemplo EN                       | Ejemplo ES                              | Uso                          |
|------------------------|----------------------------------|------------------------------------------|------------------------------|
| `Greeting`             | "Good morning"                   | "Buenos días"                            | Primer saludo                |
| `caller_name`          | "Alice Smith"                    | "Alice Smith"                            | Nombre para la reserva       |
| `caller_phone`         | "+44XXXXXXXXXX"                  | "+44XXXXXXXXXX"                          | Teléfono de contacto         |
| `caller_email`         | ""                               | ""                                       | Solo si lo piden             |
| `business_type`        | "restaurant"                     | "restaurante"                            | Tipo de negocio              |
| `request_type`         | "table for 4"                    | "una mesa para 4"                        | Petición corta               |
| `desired_datetime`     | "Friday 9pm"                     | "viernes 21:00"                          | Horario preferido            |
| `flexibility`          | "any evening this week"          | "cualquier noche esta semana"            | Alternativas                 |
| `special_requirements` | "high chair"                     | "trona"                                  | Requisitos especiales        |

**Primer mensaje (ES):** `{{Greeting}}, llamo de parte de {{caller_name}}, ¿podría ayudarme con {{request_type}}?`
**Primer mensaje (EN):** `{{Greeting}}, I'm calling on behalf of {{caller_name}} — would you have a moment to help with a {{request_type}}?`

---

## Notas

- **Siempre usar `conversation_initiation_client_data.dynamic_variables`** para inyectar valores. No hay otro método.
- **Las claves deben coincidir exactamente** con los `{{...}}` del system prompt del agente (sensible a mayúsculas).
- **El idioma se detecta automáticamente** en el script Python del skill, pero se puede forzar con `lang_hint="en"` o `lang_hint="es"`. Si el contacto resuelto desde `contacts.json` tiene `lang`, ése tiene prioridad sobre la detección automática.
