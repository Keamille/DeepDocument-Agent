"""
主入口：启动窗口
"""

import webview
from pathlib import Path

from deepdocument.graph.builder import build_graph
from deepdocument.ui.api import WindowAPI


def main():
    """
    启动 DeepDocument 窗口
    """
    # 构建图
    graph = build_graph()

    # 创建 API
    api = WindowAPI(graph)

    # 启动窗口
    ui_dir = Path(__file__).parent / "ui"
    index_path = ui_dir / "index.html"

    window = webview.create_window(
        "DeepDocument",
        str(index_path),
        js_api=api,
        width=1600,
        height=1000,
        resizable=True,
    )

    webview.start(debug=True)


if __name__ == "__main__":
    main()
