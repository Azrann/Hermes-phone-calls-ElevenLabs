"""
Hermes Contacts — Resolver de aliases a contactos
==================================================

Lee ~/.hermes/contacts.json y resuelve aliases como "mamá", "mi mujer",
"tío Pepe" → contacto completo (incluyendo el `name` que se usa en el
saludo de la llamada).

Modelo:
- `aliases` es la ÚNICA fuente de matching (junto con `id` y `relationship`).
- `name` se usa SOLO para el saludo del agente ("Hola Isabel"). El agente
  nunca dirá "Hola mamá" — dirá "Hola Isabel" aunque el usuario haya
  dicho "llama a mamá".
- Si quieres que el nombre también valga para buscar (caso típico de
  amigos), añádelo explícitamente a `aliases`.

Política de resolución:
- 1 match → devuelve el contacto.
- 0 matches → ContactNotFound.
- 2+ matches → AmbiguousContact (con la lista, para que
  el LLM o el usuario decida).

Formato de contacts.json:

    {
      "contacts": [
        {
          "id": "mother",
          "name": "Isabel",
          "phone": "+34XXXXXXXXX",
          "relationship": "mi madre",
          "lang": "es",
          "aliases": ["mamá", "mami", "madre", "ama"]
        },
        {
          "id": "friend_john",
          "name": "John",
          "phone": "+44XXXXXXXXX",
          "relationship": "colleague",
          "lang": "en",
          "aliases": ["John", "Johnny", "John Smith"]
        }
      ]
    }
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional

CONTACTS_PATH = Path(os.environ.get(
    "HERMES_CONTACTS_PATH",
    os.path.expanduser("~/.hermes/contacts.json"),
))


class ContactError(Exception):
    """Base para errores de resolución de contactos."""


class ContactNotFound(ContactError):
    def __init__(self, query: str):
        super().__init__(f"No contact found for: {query!r}")
        self.query = query


class AmbiguousContact(ContactError):
    def __init__(self, query: str, matches: list):
        names = ", ".join(_describe(m) for m in matches)
        super().__init__(
            f"Ambiguous contact for {query!r} — {len(matches)} matches: {names}. "
            f"Please disambiguate (use a more specific alias or the id)."
        )
        self.query = query
        self.matches = matches


def _describe(c: dict) -> str:
    rel = c.get("relationship", "")
    return f"{c['name']} ({rel})" if rel else c["name"]


def _normalize(s: str) -> str:
    """Lowercase + sin acentos + sin puntuación + colapsa espacios."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"[^\w\s+]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _search_keys(contact: dict) -> list:
    """Strings normalizados por los que se puede invocar al contacto.

    Importante: `name` NO entra aquí — solo se usa para el saludo.
    Si quieres que el nombre también funcione como alias de búsqueda,
    añádelo explícitamente a la lista `aliases` del contacto.
    """
    out = []
    if contact.get("id"):
        out.append(_normalize(contact["id"]))
    if contact.get("relationship"):
        out.append(_normalize(contact["relationship"]))
    for alias in contact.get("aliases", []) or []:
        if alias:
            out.append(_normalize(alias))
    # Dedupe preservando orden
    seen = set()
    uniq = []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def _load_contacts() -> list:
    if not CONTACTS_PATH.exists():
        return []
    try:
        data = json.loads(CONTACTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContactError(f"Invalid JSON in {CONTACTS_PATH}: {e}")
    contacts = data.get("contacts", []) if isinstance(data, dict) else data
    if not isinstance(contacts, list):
        raise ContactError(f"{CONTACTS_PATH} must contain a list of contacts")
    for c in contacts:
        if not isinstance(c, dict) or not c.get("name") or not c.get("phone"):
            raise ContactError(f"Invalid contact entry (needs name+phone): {c}")
    return contacts


# Verbos/preámbulos que se quitan del query: "llama a Elena" → "elena"
_PREAMBLES = (
    "llama a la", "llama al", "llama a",
    "llamar a la", "llamar al", "llamar a",
    "dile a la", "dile al", "dile a",
    "decirle a la", "decirle al", "decirle a",
    "call to", "call", "phone", "tell",
    "a la", "al", "a", "to",
)


def _strip_preambles(q: str) -> str:
    """Quita preámbulos comunes iterativamente. 'llama a la' → ''."""
    changed = True
    while changed:
        changed = False
        for pre in _PREAMBLES:
            if q == pre or q.startswith(pre + " "):
                q = q[len(pre):].strip()
                changed = True
                break
    return q


def resolve(query: str) -> dict:
    """Resuelve un alias/relationship/id a un único contacto.

    Lanza:
      - ContactNotFound  si no hay matches.
      - AmbiguousContact si hay 2+ matches (nunca llama al equivocado).

    Estrategia (pase a pase, primer pase con resultados gana):
      1. Match exacto contra search keys (id/relationship/aliases).
      2. Match exacto sin "mi " inicial (por si el alias es "madre"
         y el usuario dijo "mi madre", o viceversa).
      3. Match por subcadena de palabra completa (ej: query "Pepe"
         matchea alias "tío Pepe").
    """
    if not query or not query.strip():
        raise ContactNotFound(query)

    contacts = _load_contacts()
    if not contacts:
        raise ContactNotFound(query)

    q = _normalize(query)
    q = _strip_preambles(q)

    if not q:
        raise ContactNotFound(query)

    # Pase 1: match exacto
    matches = [c for c in contacts if q in _search_keys(c)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousContact(query, matches)

    # Pase 2: variantes con/sin "mi "
    if q.startswith("mi "):
        q_alt = q[3:].strip()
    else:
        q_alt = "mi " + q
    matches = [c for c in contacts if q_alt in _search_keys(c)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousContact(query, matches)

    # Pase 3: subcadena por palabras completas
    q_words = set(q.split())
    if q_words:
        word_matches = []
        seen_ids = set()
        for c in contacts:
            for key in _search_keys(c):
                key_words = set(key.split())
                if q_words.issubset(key_words):
                    if id(c) not in seen_ids:
                        seen_ids.add(id(c))
                        word_matches.append(c)
                    break
        if len(word_matches) == 1:
            return word_matches[0]
        if len(word_matches) > 1:
            raise AmbiguousContact(query, word_matches)

    raise ContactNotFound(query)


def list_all() -> list:
    """Devuelve todos los contactos (para listados de UI o debugging)."""
    return _load_contacts()


def lookup(query: str) -> Optional[dict]:
    """Versión que no lanza — devuelve None si no resuelve unívocamente."""
    try:
        return resolve(query)
    except ContactError:
        return None
