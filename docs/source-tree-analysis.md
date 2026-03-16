# 源代码树分析

**项目：** 临床辅助诊断智能体（IDA MVP）
**生成日期：** 2026-03-16
**扫描级别：** 快速扫描（模式匹配）

---

## 目录结构总览

```
medic_agent_mvp/                        # 项目根目录
├── index.html                          # Vite 入口 HTML（前端）
├── vite.config.js                      # Vite 构建配置（含 /api 代理到 :8000）
├── package.json                        # 前端依赖（React 18, Vite 5）
├── requirements.txt                    # 后端依赖（FastAPI, Uvicorn, Pydantic, Anthropic SDK）
├── server.py                           # ⭐ 后端主入口（FastAPI 应用）
│
├── src/                                # 源代码目录（前后端共用）
│   ├── main.jsx                        # ⭐ React 前端入口
│   ├── ida-diagnostic-mvp.jsx          # ⭐ IDA 诊断主 UI 组件
│   └── ida/                            # ⭐ IDA 诊断核心 Python 包
│       ├── __init__.py                 # 包初始化
│       ├── engine.py                   # ⭐ 诊断规则引擎（条款 0~9 判断逻辑）
│       ├── models.py                   # ⭐ Pydantic 数据模型（输入/输出 Schema）
│       └── reference.py                # ⭐ 参考区间配置（WS/T 405 标准）
│
├── tests/                              # 后端测试
│   └── test_engine.py                  # ⭐ 引擎单元测试
│
├── doc/                                # 项目文档（领域知识）
│   ├── prd.md                          # 产品需求文档（V1.0）
│   ├── 缺铁性平血诊断流程.md              # IDA 诊断逻辑伪代码（文字版 + Python 版）
│   └── 临床辅助诊断智能体_需求分析与方案设计.docx
│
├── docs/                               # AI 上下文文档（本目录）
│   └── index.md                        # 文档主索引
│
├── dist/                               # 前端构建输出（Vite build）
│   ├── index.html
│   └── assets/
│
└── _bmad/                              # BMAD 工作流配置（非业务代码）
```

---

## 关键目录说明

| 目录/文件 | 职责 | 所属部分 |
|-----------|------|----------|
| `server.py` | FastAPI 应用主文件，定义 `/api/*` 路由，处理 HTTP 请求，调用诊断引擎 | backend |
| `src/ida/engine.py` | 纯规则引擎，实现条款 0~9 判断逻辑，JSON in → JSON out，无 LLM 依赖 | backend |
| `src/ida/models.py` | Pydantic 模型：患者输入 Schema、诊断输出 Schema | backend |
| `src/ida/reference.py` | WS/T 405 参考区间配置，支持版本化管理 | backend |
| `src/ida-diagnostic-mvp.jsx` | React 主 UI 组件：表单输入、API 调用、诊断结果展示 | frontend |
| `src/main.jsx` | React 应用挂载入口 | frontend |
| `tests/test_engine.py` | 引擎单元测试，验证各诊断路径（确诊/提示/阴性/不适用） | backend |

---

## 集成点

前端（Vite dev server, :5173）通过以下代理与后端通信：

```
前端 /api/* → http://localhost:8000/api/*（FastAPI 后端）
```

生产环境：前端构建为静态文件，由 FastAPI 直接静态服务（或反向代理部署）。
