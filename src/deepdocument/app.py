"""
应用入口

打开桌面窗口，初始化 LangGraph，处理用户交互。
"""

import os
import sys
from pathlib import Path

import webview
from dotenv import load_dotenv

from deepdocument.graph.builder import build_graph
from deepdocument.ui.api import WindowAPI


def main():
    """启动 DeepDocument 桌面应用"""
    # 加载环境变量
    load_dotenv()

    # 验证必需的环境变量
    required_env = ["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"]
    missing = [k for k in required_env if not os.getenv(k)]
    if missing:
        print(f"错误: 缺少环境变量 {', '.join(missing)}", file=sys.stderr)
        print("请复制 .env.example 为 .env 并填写配置", file=sys.stderr)
        sys.exit(1)

    # 确保数据目录存在
    projects_dir = Path("projects")
    projects_dir.mkdir(exist_ok=True)
    (projects_dir / ".gitkeep").touch()

    skills_dir = Path("skills_user")
    skills_dir.mkdir(exist_ok=True)

    # 构建图
    graph = build_graph()

    # 创建窗口 API
    api = WindowAPI(graph)

    # 启动窗口
    html_path = Path(__file__).parent / "ui" / "index.html"
    window = webview.create_window(
        title="DeepDocument",
        url=str(html_path),
        js_api=api,
        width=1400,
        height=900,
        resizable=True,
    )

    webview.start(debug=os.getenv("DEBUG", "").lower() == "true")


if __name__ == "__main__":
    main()
