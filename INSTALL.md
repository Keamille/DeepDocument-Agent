# DeepDocument

文献综述助手 —— 本机客户端，基于 LangGraph 和 pywebview。

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd DeepDocument-agent

# 安装依赖（建议用虚拟环境）
pip install -e .

# 开发依赖
pip install -e ".[dev]"
```

## 配置

复制 `.env.example` 为 `.env`，填入 OpenAI 兼容接口的配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
```

## 运行

```bash
deepdocument
```

或直接运行：

```bash
python src/deepdocument/main.py
```

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black src tests
ruff check src tests
```

## 架构

详见 `docs/` 目录：

1. `architecture.md` — 整体架构
2. `document-model.md` — 数据模型
3. `agent-loop.md` — 循环流程
4. `memory.md` — 提示预算
5. `skills.md` — 扩展机制
6. `gui.md` — 窗口交互
7. `stack.md` — 技术选型
