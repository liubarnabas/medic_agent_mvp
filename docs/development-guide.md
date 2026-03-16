# 开发指南

**项目：** 临床辅助诊断智能体（IDA MVP）
**生成日期：** 2026-03-16

---

## 前置条件

| 工具 | 版本要求 |
|------|----------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

---

## 环境配置

### 后端依赖安装

```bash
pip install -r requirements.txt
```

**requirements.txt 内容：**
```
pydantic>=2.0
pytest>=7.0
fastapi>=0.111
uvicorn[standard]>=0.30
anthropic>=0.30
```

### 前端依赖安装

```bash
npm install
```

### 环境变量

Anthropic SDK 需要 API Key：
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

---

## 本地开发

### 启动后端（FastAPI）

```bash
uvicorn server:app --reload --port 8000
```

后端运行于：http://localhost:8000

### 启动前端（Vite）

```bash
npm run dev
```

前端运行于：http://localhost:5173（自动代理 `/api/*` → `:8000`）

---

## 测试

### 运行后端单元测试

```bash
pytest tests/
```

或指定测试文件：

```bash
pytest tests/test_engine.py -v
```

### 测试覆盖范围

`tests/test_engine.py` 应覆盖以下诊断路径：

| 路径 | 测试场景 |
|------|----------|
| 确诊 IDA | 小细胞低色素 + ≥2 条阳性（如 SF↓ + TS↓） |
| 高度提示 | SF < 14 μg/L，未达确诊标准 |
| 证据不足 | SF ≥ 14，条款 < 2 |
| 不适用 | precondition = True |
| 非贫血 | Hb ≥ 参考下限 |

---

## 构建前端

```bash
npm run build
```

构建输出至 `dist/`，可由 FastAPI 静态文件服务：

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="dist", html=True), name="static")
```

---

## 项目结构快速参考

```
server.py           FastAPI 主文件（API 路由）
src/ida/
  engine.py         规则引擎（⭐ 核心业务逻辑）
  models.py         Pydantic 数据模型
  reference.py      WS/T 405 参考区间配置
src/
  main.jsx          React 入口
  ida-diagnostic-mvp.jsx  主 UI 组件
tests/
  test_engine.py    引擎单元测试
doc/
  prd.md            产品需求文档
  缺铁性平血诊断流程.md  IDA 诊断逻辑详细说明
```

---

## 常见任务

### 修改诊断阈值

编辑 `src/ida/reference.py`，更新 WS/T 405 参考区间值。

### 新增检验指标

1. 在 `src/ida/models.py` 中添加 Pydantic 字段
2. 在 `src/ida/engine.py` 中添加对应条款判断逻辑
3. 更新 `src/ida-diagnostic-mvp.jsx` 表单输入
4. 补充 `tests/test_engine.py` 测试用例

### 扩展新病种

参考 `doc/prd.md` 第 10 节"疾病扩展模板"，按模板填充新病种的诊断规则。
