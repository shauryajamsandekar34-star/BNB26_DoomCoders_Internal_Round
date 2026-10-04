import os
import httpx

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI()

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
TOKEN = os.getenv("TRANSLATION_PROXY_TOKEN", "")


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: dict | None = None


@app.post("/api/generate")
async def generate(
    request: GenerateRequest,
    authorization: str | None = Header(default=None)
):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            OLLAMA_URL,
            json=request.model_dump()
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type="application/json"
    )