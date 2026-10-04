import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI(title="Roundtable Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate"
)

OLLAMA_TOKEN = os.getenv(
    "OLLAMA_TOKEN",
    ""
)

OLLAMA_MODEL = "translategemma:4b"


# --------------------------------------------------
# ROOM STORAGE
# --------------------------------------------------

rooms: Dict[str, Dict[str, Any]] = {}

translation_cache: Dict[str, str] = {}

last_translation_error = ""


# --------------------------------------------------
# LANGUAGE NAMES
# --------------------------------------------------

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "gu": "Gujarati",
    "bn": "Bengali",
}


# --------------------------------------------------
# TRANSLATION
# --------------------------------------------------

async def translate_text(
    text: str,
    source_language: str,
    target_language: str,
) -> str:

    global last_translation_error

    text = text.strip()

    if not text:
        return text

    if source_language == target_language:
        return text

    cache_key = (
        f"{source_language}:"
        f"{target_language}:"
        f"{text.lower()}"
    )

    if cache_key in translation_cache:
        return translation_cache[cache_key]

    source_name = LANGUAGE_NAMES.get(
        source_language,
        source_language,
    )

    target_name = LANGUAGE_NAMES.get(
        target_language,
        target_language,
    )

    prompt = f"""
You are a professional real-time translator.

Translate the complete conversation caption from {source_name} to {target_name}.

Rules:
- Translate the complete sentence.
- Do not leave source-language words untranslated unless they are proper names.
- Preserve people's names.
- Preserve numbers.
- Preserve important technical terms when appropriate.
- Preserve the original meaning.
- Use natural conversational language.
- Do not explain the translation.
- Do not answer the speaker.
- Do not add information.
- Return ONLY the translated sentence.
- Do not use quotation marks.

Source language: {source_name}
Target language: {target_name}

Text:
{text}
""".strip()

    try:

        headers = {
            "Content-Type": "application/json"
        }

        if OLLAMA_TOKEN:

            headers["Authorization"] = (
                f"Bearer {OLLAMA_TOKEN}"
            )

        print("--------------------------------")
        print("TRANSLATION REQUEST")
        print("URL:", OLLAMA_URL)
        print("MODEL:", OLLAMA_MODEL)
        print(
            "LANGUAGE:",
            source_language,
            "->",
            target_language
        )
        print("TEXT:", text)

        async with httpx.AsyncClient(
            timeout=90.0
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                headers=headers,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1
                    },
                },
            )

        print(
            "OLLAMA STATUS:",
            response.status_code
        )

        if response.status_code != 200:

            error_message = (
                f"Ollama HTTP "
                f"{response.status_code}: "
                f"{response.text[:500]}"
            )

            last_translation_error = (
                error_message
            )

            print(
                "OLLAMA ERROR:",
                error_message
            )

            return text

        try:

            data = response.json()

        except Exception as exc:

            error_message = (
                "Invalid JSON from Ollama: "
                + repr(exc)
            )

            last_translation_error = (
                error_message
            )

            print(
                error_message
            )

            return text

        translated_text = str(
            data.get(
                "response",
                ""
            )
        ).strip()

        if not translated_text:

            error_message = (
                "Ollama returned empty response"
            )

            last_translation_error = (
                error_message
            )

            print(
                error_message
            )

            return text

        # Remove accidental surrounding quotes
        if (
            len(translated_text) >= 2
            and translated_text[0] == '"'
            and translated_text[-1] == '"'
        ):

            translated_text = (
                translated_text[1:-1]
                .strip()
            )

        translation_cache[
            cache_key
        ] = translated_text

        last_translation_error = ""

        print(
            "TRANSLATION SUCCESS:",
            translated_text
        )

        print("--------------------------------")

        return translated_text

    except httpx.TimeoutException as exc:

        last_translation_error = (
            "Ollama request timed out: "
            + repr(exc)
        )

        print(
            "TRANSLATION TIMEOUT:",
            repr(exc)
        )

        return text

    except httpx.ConnectError as exc:

        last_translation_error = (
            "Could not connect to Ollama: "
            + repr(exc)
        )

        print(
            "TRANSLATION CONNECTION ERROR:",
            repr(exc)
        )

        return text

    except Exception as exc:

        last_translation_error = (
            "Translation exception: "
            + repr(exc)
        )

        print(
            "TRANSLATION ERROR:",
            repr(exc)
        )

        return text


# --------------------------------------------------
# HEALTH
# --------------------------------------------------

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "ollama_model": OLLAMA_MODEL,
        "ollama_url_configured": bool(OLLAMA_URL),
        "ollama_token_configured": bool(
            OLLAMA_TOKEN
        ),
        "rooms": len(rooms),
    }


# --------------------------------------------------
# TRANSLATION TEST
# --------------------------------------------------

@app.get("/test-translation")
async def test_translation(
    text: str = "नमस्ते, आप कैसे हैं?",
    source: str = "hi",
    target: str = "en",
):

    translated = await translate_text(
        text,
        source,
        target,
    )

    return {
        "source": text,
        "source_language": source,
        "target_language": target,
        "translation": translated,
        "translated": translated != text,
        "error": last_translation_error or None,
    }


# --------------------------------------------------
# TRANSLATION STATUS
# --------------------------------------------------

@app.get("/translation-status")
async def translation_status():

    return {
        "ollama_url": OLLAMA_URL,
        "model": OLLAMA_MODEL,
        "token_configured": bool(
            OLLAMA_TOKEN
        ),
        "last_error": (
            last_translation_error
            or None
        ),
        "cache_entries": len(
            translation_cache
        ),
    }


# --------------------------------------------------
# OLLAMA STATUS
# --------------------------------------------------

@app.get("/ollama")
async def ollama_status():

    try:

        async with httpx.AsyncClient(
            timeout=5
        ) as client:

            response = await client.get(
                "http://127.0.0.1:11434/api/tags"
            )

        if response.status_code != 200:

            return {
                "connected": False,
                "error": response.text,
            }

        data = response.json()

        models = [
            model.get("name")
            for model in data.get(
                "models",
                []
            )
        ]

        return {
            "connected": True,
            "models": models,
            "selected_model": OLLAMA_MODEL,
        }

    except Exception as exc:

        return {
            "connected": False,
            "error": str(exc),
        }


# --------------------------------------------------
# ROOM HELPERS
# --------------------------------------------------

def get_room(room_code: str):

    if room_code not in rooms:

        rooms[room_code] = {
            "participants": {},
            "connections": {},
        }

    return rooms[room_code]


async def broadcast(
    room_code: str,
    message: dict,
    exclude_client: str | None = None,
):

    room = rooms.get(room_code)

    if not room:
        return

    disconnected = []

    for client_id, websocket in room[
        "connections"
    ].items():

        if client_id == exclude_client:
            continue

        try:

            await websocket.send_json(
                message
            )

        except Exception:

            disconnected.append(
                client_id
            )

    for client_id in disconnected:

        room["connections"].pop(
            client_id,
            None
        )

        room["participants"].pop(
            client_id,
            None
        )


async def send_participants(
    room_code: str
):

    room = rooms.get(room_code)

    if not room:
        return

    participants = []

    for client_id, participant in room[
        "participants"
    ].items():

        participants.append({
            "client_id": client_id,
            "name": participant["name"],
            "language": participant["language"],
            "caption_language": participant[
                "caption_language"
            ],
        })

    await broadcast(
        room_code,
        {
            "type": "participants",
            "participants": participants,
        },
    )


# --------------------------------------------------
# WEBSOCKET
# --------------------------------------------------

@app.websocket("/ws/{room_code}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_code: str,
):

    await websocket.accept()

    client_id = websocket.query_params.get(
        "client_id"
    ) or str(uuid.uuid4())

    name = websocket.query_params.get(
        "name",
        "Participant",
    )

    language = websocket.query_params.get(
        "language",
        "en",
    )

    caption_language = (
        websocket.query_params.get(
            "caption_language",
            "en",
        )
    )

    room = get_room(room_code)

    room["connections"][
        client_id
    ] = websocket

    room["participants"][
        client_id
    ] = {
        "name": name,
        "language": language,
        "caption_language": caption_language,
        "joined_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    print(
        f"{name} joined room "
        f"{room_code} "
        f"({client_id})"
    )

    await websocket.send_json({
        "type": "connected",
        "client_id": client_id,
        "room": room_code,
    })

    await send_participants(
        room_code
    )

    try:

        while True:

            message = (
                await websocket.receive_json()
            )

            message_type = message.get(
                "type",
                "",
            )

            # ------------------------------------------
            # SETTINGS
            # ------------------------------------------

            if message_type == "settings":

                participant = room[
                    "participants"
                ].get(client_id)

                if participant:

                    if message.get("name"):

                        participant["name"] = (
                            message["name"]
                        )

                    if message.get("language"):

                        participant["language"] = (
                            message["language"]
                        )

                    if message.get(
                        "caption_language"
                    ):

                        participant[
                            "caption_language"
                        ] = message[
                            "caption_language"
                        ]

                await send_participants(
                    room_code
                )

            # ------------------------------------------
            # CAPTION
            # ------------------------------------------

            elif message_type in (
                "caption",
                "transcript",
            ):

                text = str(
                    message.get(
                        "text",
                        "",
                    )
                ).strip()

                if not text:
                    continue

                participant = room[
                    "participants"
                ].get(client_id)

                if not participant:
                    continue

                source_language = (
                    message.get(
                        "source_language",
                        participant["language"],
                    )
                )

                caption_id = (
                    message.get(
                        "caption_id"
                    )
                    or str(uuid.uuid4())
                )

                timestamp = message.get(
                    "timestamp"
                )

                if timestamp is None:

                    timestamp = datetime.now(
                        timezone.utc
                    ).isoformat()

                # --------------------------------------
                # SEND TO EVERY PARTICIPANT
                # --------------------------------------

                for (
                    target_client_id,
                    target_socket
                ) in list(
                    room["connections"].items()
                ):

                    target_participant = room[
                        "participants"
                    ].get(
                        target_client_id
                    )

                    if not target_participant:
                        continue

                    target_language = (
                        target_participant[
                            "caption_language"
                        ]
                    )

                    translated_text = (
                        await translate_text(
                            text,
                            source_language,
                            target_language,
                        )
                    )

                    outgoing = {
                        "type": "caption",
                        "caption_id": caption_id,
                        "speaker_id": client_id,
                        "speaker": participant[
                            "name"
                        ],
                        "source_language": (
                            source_language
                        ),
                        "target_language": (
                            target_language
                        ),
                        "original_text": text,
                        "text": translated_text,
                        "timestamp": timestamp,
                    }

                    try:

                        await target_socket.send_json(
                            outgoing
                        )

                    except Exception as exc:

                        print(
                            "Caption send error:",
                            repr(exc)
                        )

            # ------------------------------------------
            # REACTION
            # ------------------------------------------

            elif message_type == "reaction":

                reaction = str(
                    message.get(
                        "reaction",
                        "",
                    )
                ).strip()

                if not reaction:
                    continue

                participant = room[
                    "participants"
                ].get(client_id)

                if not participant:
                    continue

                await broadcast(
                    room_code,
                    {
                        "type": "reaction",
                        "client_id": client_id,
                        "name": participant[
                            "name"
                        ],
                        "reaction": reaction,
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    },
                )

            # ------------------------------------------
            # PING
            # ------------------------------------------

            elif message_type == "ping":

                await websocket.send_json({
                    "type": "pong"
                })

    except WebSocketDisconnect:

        print(
            f"{name} left room "
            f"{room_code}"
        )

    except Exception as exc:

        print(
            "WebSocket error:",
            repr(exc)
        )

    finally:

        room["connections"].pop(
            client_id,
            None
        )

        room["participants"].pop(
            client_id,
            None
        )

        if room["connections"]:

            await send_participants(
                room_code
            )

        else:

            rooms.pop(
                room_code,
                None
            )


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

@app.on_event("startup")
async def startup_event():

    print("--------------------------------")
    print("Roundtable backend started")
    print("Ollama URL:", OLLAMA_URL)
    print(
        "Ollama token configured:",
        bool(OLLAMA_TOKEN)
    )
    print("Ollama model:", OLLAMA_MODEL)
    print("--------------------------------")