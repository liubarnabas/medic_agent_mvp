# 项目文档索引

**项目：** 临床辅助诊断智能体（Clinical Diagnostic AI Agent · IDA MVP）
**生成日期：** 2026-03-16
**扫描级别：** 快速扫描

---

## 项目概览

- **仓库类型：** 多部分（Multi-Part）
- **主语言：** Python + JavaScript
- **架构模式：** 计算链路 + 检索链路 + 融合决策（三层诊断架构）
- **MVP 范围：** 缺铁性贫血（IDA）诊断通路

### 快速参考

#### Frontend（React SPA）
- **类型：** Web 前端
- **技术栈：** React 18 + Vite 5
- **入口：** `src/main.jsx`

#### Backend（Python FastAPI）
- **类型：** REST API 后端
- **技术栈：** FastAPI + Uvicorn + Pydantic + Anthropic SDK
- **入口：** `server.py`
- **核心：** `src/ida/engine.py`（纯规则诊断引擎）

---

## 生成的文档

- [项目概述](./project-overview.md) — 产品定位、技术栈、里程碑
- [架构文档 — 后端](./architecture-backend.md) — FastAPI、三层架构、诊断逻辑、数据模型
- [架构文档 — 前端](./architecture-frontend.md) — React 组件、数据流、构建部署
- [源代码树分析](./source-tree-analysis.md) — 目录结构注释、集成点
- [组件清单 — 前端](./component-inventory-frontend.md) — React 组件列表
- [集成架构](./integration-architecture.md) — 前后端通信、API 规范、外部依赖
- [开发指南](./development-guide.md) — 环境配置、本地启动、测试、常见任务
- [API 合约 — 后端](./api-contracts-backend.md) _(To be generated)_
- [数据模型 — 后端](./data-models-backend.md) _(To be generated)_

---

## 已有文档

- [PRD — 产品需求文档](../doc/prd.md) — V1.0，含完整功能需求、数据规格、验收标准
- [IDA 诊断逻辑详解](../doc/缺铁性平血诊断流程.md) — 文字版 + Python 伪代码，供医生核对
- [需求分析与方案设计](../doc/临床辅助诊断智能体_需求分析与方案设计.docx) — 原始设计文档

---

## 快速开始

### 启动后端
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_api_key
uvicorn server:app --reload --port 8000
```

### 启动前端
```bash
npm install
npm run dev
# 访问 http://localhost:5173
```

### 运行测试
```bash
pytest tests/ -v
```

---

> 👆 本文件是 AI 辅助开发的主要入口文档。在创建新功能或 PRD 时，请将此 index.md 作为项目上下文参考。
