"""
FastAPI 后端 — 代理 Anthropic LLM 调用
运行: uvicorn server:app --reload --port 8000
环境变量: ANTHROPIC_API_KEY
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

app = FastAPI(title="IDA Diagnostic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY 环境变量未设置，LLM 功能不可用"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    text: str


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    client = get_client()

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": req.prompt}],
    )

    text = "".join(block.text for block in message.content if hasattr(block, "text"))
    return GenerateResponse(text=text)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_ready": bool(os.environ.get("ANTHROPIC_API_KEY"))}
