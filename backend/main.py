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

OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")

OLLAMA_MODEL = "translategemma:4b"


# --------------------------------------------------
# ROOM STORAGE
# --------------------------------------------------

rooms: Dict[str, Dict[str, Any]] = {}

translation_cache: Dict[str, str] = {}


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

Strict rules:
- Translate the ENTIRE sentence.
- Do not leave words from the source language untranslated.
- Do not copy unfamiliar words into the output just because you do not recognize them.
- Preserve the meaning and context of the complete sentence.
- Preserve people's names exactly.
- Preserve numbers and important technical terms when appropriate.
- If the input contains mixed languages, translate all understandable words into the target language.
- Use natural conversational language.
- Do not explain the translation.
- Do not answer the speaker.
- Do not add information.
- Return ONLY the final translated sentence.
- Do not use quotation marks.

Source language: {source_name}
Target language: {target_name}

Text:
{text}
""".strip()

    try:

        headers = {}

        if OLLAMA_TOKEN:
            headers["Authorization"] = (
                f"Bearer {OLLAMA_TOKEN}"
            )

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
            "Ollama response:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "Ollama error:",
                response.text
            )

            return text

        data = response.json()

        translated_text = data.get(
            "response",
            ""
        ).strip()

        if not translated_text:

            print(
                "Ollama returned empty translation"
            )

            return text

        translation_cache[
            cache_key
        ] = translated_text

        print(
            f"Translated "
            f"[{source_language} -> {target_language}]: "
            f"{text} -> {translated_text}"
        )

        return translated_text

    except Exception as exc:

        print(
            "Ollama translation error:",
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
            # UPDATE PARTICIPANT SETTINGS
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
            # LIVE CAPTION
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
                # Send caption separately to every
                # participant using their preferred
                # caption language.
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
# STARTUP MESSAGE
# --------------------------------------------------

@app.on_event("startup")
async def startup_event():

    print("--------------------------------")
    print("Roundtable backend started")
    print("Ollama URL:", OLLAMA_URL)
    print("Ollama model:", OLLAMA_MODEL)
    print("--------------------------------")