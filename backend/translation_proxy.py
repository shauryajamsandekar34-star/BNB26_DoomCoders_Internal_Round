import os
import re

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI()

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate"
)

TOKEN = os.getenv("TRANSLATION_PROXY_TOKEN", "")

LANGUAGE_CODES = {
    "English": "en",
    "Hindi": "hi",
    "Marathi": "mr",
    "Tamil": "ta",
    "Telugu": "te",
    "Kannada": "kn",
    "Gujarati": "gu",
    "Bengali": "bn",
}


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: dict | None = None


def clean_language_name(value):
    value = value.strip()

    for name in LANGUAGE_CODES:
        if value.lower() == name.lower():
            return name

    return value


def extract_prompt_details(prompt: str):
    source_name = None
    target_name = None
    text = None

    # Format 1:
    # Source language: Hindi
    # Target language: English
    source_match = re.search(
        r"Source language:\s*(.+)",
        prompt,
        re.IGNORECASE
    )

    target_match = re.search(
        r"Target language:\s*(.+)",
        prompt,
        re.IGNORECASE
    )

    if source_match:
        source_name = clean_language_name(source_match.group(1))

    if target_match:
        target_name = clean_language_name(target_match.group(1))

    # Format 2:
    # professional Hindi (hi) to English (en) translator
    if not source_name or not target_name:
        language_match = re.search(
            r"professional\s+(.+?)\s*\(([a-z]{2})\)\s+to\s+(.+?)\s*\(([a-z]{2})\)\s+translator",
            prompt,
            re.IGNORECASE
        )

        if language_match:
            source_name = clean_language_name(
                language_match.group(1)
            )
            target_name = clean_language_name(
                language_match.group(3)
            )

    # Format 1 text:
    # Text:
    # actual text
    text_match = re.search(
        r"(?:^|\n)Text:\s*\n?(.*)",
        prompt,
        re.IGNORECASE | re.DOTALL
    )

    if text_match:
        text = text_match.group(1).strip()

    # Format 2 text:
    # The actual translation text comes after the final blank line.
    if not text:
        paragraphs = re.split(r"\n\s*\n", prompt.strip())

        if len(paragraphs) >= 2:
            possible_text = paragraphs[-1].strip()

            if (
                possible_text
                and not possible_text.lower().startswith("please translate")
                and not possible_text.lower().startswith("produce only")
            ):
                text = possible_text

    if not source_name:
        source_name = "English"

    if not target_name:
        target_name = "English"

    return source_name, target_name, text or ""


def build_translate_gemma_prompt(
    source_name: str,
    target_name: str,
    text: str
):
    source_code = LANGUAGE_CODES.get(
        source_name,
        source_name.lower()[:2]
    )

    target_code = LANGUAGE_CODES.get(
        target_name,
        target_name.lower()[:2]
    )

    return f"""You are a professional {source_name} ({source_code}) to {target_name} ({target_code}) translator. Your goal is to accurately convey the meaning and nuances of the original {source_name} text while adhering to {target_name} grammar, vocabulary, and cultural sensitivities.
Produce only the {target_name} translation, without any additional explanations or commentary. Please translate the following {source_name} text into {target_name}:


{text}"""


@app.post("/api/generate")
async def generate(
    request: GenerateRequest,
    authorization: str | None = Header(default=None)
):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    source_name, target_name, text = extract_prompt_details(
        request.prompt
    )

    if not text:
        print("Could not extract text.")
        print("Incoming prompt:")
        print(request.prompt)

        raise HTTPException(
            status_code=400,
            detail="Could not extract translation text"
        )

    translate_prompt = build_translate_gemma_prompt(
        source_name,
        target_name,
        text
    )

    print("--------------------------------")
    print("Translation proxy request")
    print("Source:", source_name)
    print("Target:", target_name)
    print("Text:", text)
    print("--------------------------------")

    payload = {
        "model": request.model,
        "prompt": translate_prompt,
        "stream": request.stream,
    }

    if request.options is not None:
        payload["options"] = request.options

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json=payload
            )

        print("Ollama status:", response.status_code)

        if response.status_code != 200:
            print("Ollama error:", response.text)

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type="application/json"
        )

    except Exception as exc:
        print("Proxy error:", repr(exc))

        raise HTTPException(
            status_code=502,
            detail=f"Ollama connection failed: {exc}"
        )