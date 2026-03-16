# 集成架构

**项目：** 临床辅助诊断智能体（IDA MVP）
**生成日期：** 2026-03-16

---

## 部分间通信

### 集成点总览

| 来源 | 目标 | 类型 | 端点 | 数据格式 |
|------|------|------|------|----------|
| frontend | backend | REST API | `POST /api/diagnose` | JSON |
| frontend | backend | 静态文件服务（生产） | `GET /*` | HTML/JS/CSS |

---

## 开发环境架构

```
浏览器（用户）
    │
    ▼
Vite Dev Server (:5173)
    │
    ├── 静态资源（/src, /index.html）→ Vite 直接服务
    │
    └── /api/* 请求 → 代理 → FastAPI (:8000)
                                    │
                                    ▼
                              计算链路（engine.py）
                                    │
                              检索链路（Anthropic API）
                                    │
                              融合决策 → 返回 JSON
```

**代理配置（vite.config.js）：**
```js
proxy: {
  "/api": {
    target: "http://localhost:8000",
    changeOrigin: true,
  }
}
```

---

## 生产环境架构

```
浏览器（用户）
    │
    ▼
FastAPI (:8000)
    │
    ├── GET /* → StaticFiles（dist/ 目录）
    │
    └── POST /api/diagnose → 诊断逻辑 → 返回 JSON
```

或使用反向代理（Nginx）：

```
Nginx
    ├── /* → dist/（静态文件）
    └── /api/* → FastAPI (:8000)
```

---

## API 接口规范

### POST /api/diagnose

**请求体：** PatientInput JSON（详见 `architecture-backend.md` 数据模型）

**响应体：** DiagnosisOutput JSON（详见 `architecture-backend.md` 数据模型）

**HTTP 状态码：**
- `200 OK`：诊断成功
- `422 Unprocessable Entity`：输入校验失败（Pydantic 错误）
- `500 Internal Server Error`：服务器内部错误

---

## 外部依赖

| 依赖 | 类型 | 用途 | MVP 阶段 |
|------|------|------|----------|
| Anthropic API | 外部 HTTP | LLM 检索链路 + 自然语言描述生成 | M4（检索链路）/ M1（LLM 描述） |
| WS/T 405 标准 | 静态配置 | Hb 参考下限（在 reference.py 中硬编码，支持年度更新） | ✅ 已实现 |
