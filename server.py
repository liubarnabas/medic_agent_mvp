"""
FastAPI 后端
- /api/diagnose   : IDA 规则引擎（计算链路，无 LLM）
- /api/reference  : 参考病例库相似检索（SQLite，70% 参考集）
- /api/generate   : Anthropic LLM 代理（检索链路 / 自然语言描述）
- /api/health     : 健康检查

运行: uvicorn server:app --reload --port 8000
环境变量: ANTHROPIC_API_KEY
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

from src.ida import diagnose as ida_diagnose
from src.ida.models import DiagnosisInput
from src.data.db import ReferenceDB, DB_PATH

app = FastAPI(title="IDA Diagnostic API")

# Reference DB – opened once at startup (lazy: only if DB file exists)
_ref_db: ReferenceDB | None = None


def get_ref_db() -> ReferenceDB:
    global _ref_db
    if _ref_db is None:
        if not DB_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail="参考病例库尚未初始化，请先运行 scripts/prepare_data.py",
            )
        _ref_db = ReferenceDB(DB_PATH)
    return _ref_db

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
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


@app.post("/api/diagnose", response_model=dict)
async def diagnose(req: DiagnosisInput) -> dict:
    """
    IDA 计算链路：纯规则引擎，无 LLM。
    输入：DiagnosisInput JSON
    输出：DiagnosisOutput JSON
    """
    result = ida_diagnose(req)
    return result.model_dump()


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


@app.get("/api/reference")
def reference_similar(
    hb: float = Query(..., description="血红蛋白 g/L"),
    mcv: float = Query(..., description="平均红细胞体积 fL"),
    sex: str = Query(..., description="性别: male | female"),
    top_k: int = Query(5, ge=1, le=20),
) -> dict:
    """
    从70%参考病例库检索相似病例（按 HGB/MCV 欧氏距离排序）。
    """
    if sex not in ("male", "female"):
        raise HTTPException(status_code=400, detail="sex 必须为 male 或 female")
    db = get_ref_db()
    similar = db.find_similar(hb=hb, mcv=mcv, sex=sex, top_k=top_k)
    return {"count": len(similar), "cases": similar}


@app.get("/api/reference/stats")
def reference_stats() -> dict:
    """参考病例库统计信息。"""
    db = get_ref_db()
    return db.stats()


@app.get("/api/health")
def health():
    ref_db_ready = DB_PATH.exists()
    return {
        "status": "ok",
        "llm_ready": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "ref_db_ready": ref_db_ready,
    }
