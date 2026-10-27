"""
应用入口

打开桌面窗口，初始化 LangGraph，处理用户交互。
"""

import os
import sys
from pathlib import Path

import webview
from dotenv import load_dotenv

from deepdocument.graph.builder import build_graph, close_checkpointers
from deepdocument.ui.api import WindowAPI


def _check_env():
    """校验 .env 中必需的三项配置"""
    required_env = ["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"]
    missing = [k for k in required_env if not os.getenv(k)]
    if missing:
        print(f"错误: 缺少环境变量 {', '.join(missing)}", file=sys.stderr)
        print("请复制 .env.example 为 .env 并填写配置", file=sys.stderr)
        sys.exit(1)


def _ensure_dirs():
    """确保数据目录存在"""
    projects_dir = Path("projects")
    projects_dir.mkdir(exist_ok=True)
    (projects_dir / ".gitkeep").touch()
    Path("skills_user").mkdir(exist_ok=True)


def main():
    """启动 DeepDocument 桌面应用"""
    load_dotenv()
    _check_env()
    _ensure_dirs()

    # 图按项目懒创建：打开文稿时才编译，thread_id = slug
    api = WindowAPI(build_graph_fn=build_graph)

    html_path = Path(__file__).parent / "ui" / "index.html"
    webview.create_window(
        title="DeepDocument",
        url=str(html_path),
        js_api=api,
        width=1400,
        height=900,
        resizable=True,
    )

    try:
        webview.start(debug=os.getenv("DEBUG", "").lower() == "true")
    finally:
        close_checkpointers()


if __name__ == "__main__":
    main()
