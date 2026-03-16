# 架构文档 — 前端（React + Vite）

**项目：** 临床辅助诊断智能体（IDA MVP）
**部分：** frontend
**生成日期：** 2026-03-16

---

## 执行摘要

前端是一个轻量级 React SPA，提供 IDA 诊断数据输入表单和诊断结果展示界面。通过 Vite 代理将 `/api/*` 请求转发至 FastAPI 后端（:8000）。

---

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| UI 框架 | React | ^18.3.1 |
| 构建工具 | Vite | ^5.4.0 |
| 语言 | JavaScript/JSX | ES2020+ |
| 开发服务器端口 | 5173 | — |
| API 代理目标 | http://localhost:8000 | — |

---

## 组件架构

MVP 阶段前端极简，只有两个关键文件：

```
src/
├── main.jsx                    # React 应用入口
│   └── 挂载 <App /> 到 #root
│
└── ida-diagnostic-mvp.jsx      # 主诊断 UI 组件
    ├── 患者基本信息表单（性别、年龄、孕期、前置条件）
    ├── 检验指标输入（Hb、MCV、MCH、MCHC、SF、TS 等）
    ├── 病因与体征输入（条款 2 相关字段）
    ├── 可选指标输入（serum_iron、TIBC、CRP 等）
    ├── 提交 → POST /api/diagnose
    └── 诊断结果展示
        ├── 诊断结论与等级（确诊/提示/阴性/不适用）
        ├── 阳性证据明细
        ├── 鉴别诊断建议
        ├── 补充检查建议
        └── LLM 生成的自然语言诊断描述
```

---

## 数据流

```
用户输入表单数据
    │
    ▼
构建请求 JSON（PatientInput Schema）
    │
    ▼
POST /api/diagnose（通过 Vite 代理 → :8000）
    │
    ▼
渲染 DiagnosisOutput
```

---

## 构建与部署

| 命令 | 用途 |
|------|------|
| `npm run dev` | 启动开发服务器（:5173），自动代理 /api/* |
| `npm run build` | 构建生产静态文件到 `dist/` |
| `npm run preview` | 预览生产构建 |

**生产部署：** `dist/` 静态文件可由 FastAPI 的 `StaticFiles` 直接服务，或通过 Nginx 反向代理部署。
