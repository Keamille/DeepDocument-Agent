"""
窗口 API

pywebview 的 js_api，连接前端和图。
未完成产品能力以骨架方法占位，见各函数 docstring 中的 TODO。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from langgraph.types import Command

from deepdocument.document.exporter import export_docx
from deepdocument.document.model import Brief, Literature
from deepdocument.document import store
from deepdocument.document.template_outline import suggest_outline
from deepdocument.graph.builder import build_graph
from deepdocument.memory.profile import (
    load_profile,
    profile_to_prompt,
    save_profile,
)
from deepdocument.memory.snapshots import (
    build_conflict_report,
    capture_file_snapshots,
)
from deepdocument.skills.registry import scan_skills


class WindowAPI:
    """窗口暴露给 JavaScript 的 API"""

    def __init__(self, build_graph_fn=build_graph):
        self._build_graph = build_graph_fn
        self.current_project = None
        self._graph = None
        self.pending_confirmation = None
        self.file_snapshots: dict[str, str] = {}

    def _thread_config(self) -> dict:
        return {"configurable": {"thread_id": self.current_project}}

    def _ensure_graph(self, project_slug: str):
        if not project_slug:
            return
        if project_slug == self.current_project and self._graph is not None:
            return
        self.current_project = project_slug
        self._graph = self._build_graph(project_slug)
        self.pending_confirmation = None
        self.file_snapshots = capture_file_snapshots(project_slug)

    # ---------- 项目 ----------

    def list_projects(self) -> list[dict]:
        root = store.PROJECTS_ROOT
        if not root.exists():
            return []

        result: list[dict] = []
        for proj_dir in root.iterdir():
            if not proj_dir.is_dir() or proj_dir.name.startswith("."):
                continue
            slug = proj_dir.name
            brief = store.load_brief(slug)
            result.append(
                {
                    "slug": slug,
                    "title": (brief.title if brief and brief.title else slug),
                    "kind": brief.kind if brief else "report",
                }
            )
        return sorted(result, key=lambda p: p["slug"])

    def create_project(
        self,
        title: str,
        kind: str = "report",
        audience: str = "",
        slug: str | None = None,
    ) -> dict:
        """
        新建文稿项目：写 brief / 空大纲与 meta。

        Returns:
            {ok, slug, title, kind} 或 {ok: False, error}
        """
        title = (title or "").strip()
        if not title:
            return {"ok": False, "error": "题目不能为空"}
        if kind not in ("summary", "report", "paper"):
            kind = "report"

        project_slug = (slug or _slugify_title(title)).strip()
        if not project_slug:
            return {"ok": False, "error": "无法从题目生成 slug"}
        if store.project_dir(project_slug).exists():
            return {"ok": False, "error": f"项目已存在: {project_slug}"}

        brief = Brief(title=title, kind=kind, audience=audience or "")  # type: ignore[arg-type]
        store.create_project(project_slug, brief)

        # summary 默认可给一节「总结」；模板大纲骨架稍后由 suggest_outline 补
        if kind == "summary":
            store.save_outline(project_slug, ["总结"])
        else:
            suggested = suggest_outline(project_slug, fallback=[])
            if suggested:
                store.save_outline(project_slug, suggested)

        self._ensure_graph(project_slug)
        return {
            "ok": True,
            "slug": project_slug,
            "title": title,
            "kind": kind,
        }

    def load_project(self, slug: str) -> dict:
        slug = (slug or "").strip()
        if not slug:
            raise ValueError("project slug 不能为空")

        root = store.project_dir(slug)
        if not root.is_dir():
            raise FileNotFoundError(f"项目不存在: {slug}")

        self._ensure_graph(slug)
        self._sync_pending_from_checkpoint()
        self.file_snapshots = capture_file_snapshots(slug)

        meta = store.load_meta(slug)
        outline = store.load_outline(slug)
        sections = []
        for sec in store.get_sections(slug):
            sections.append(
                {
                    "id": sec.id,
                    "title": sec.title,
                    "status": sec.status,
                    "gist": sec.gist,
                    "content": store.load_section(slug, sec.id),
                }
            )

        literature = []
        for lit in store.load_literature(slug, status="accepted"):
            literature.append(
                {
                    "id": lit.id,
                    "title": lit.title,
                    "authors": list(lit.authors or []),
                    "year": lit.year,
                    "venue": lit.venue,
                    "url": lit.url,
                    "content_source": lit.content_source,
                }
            )

        brief = store.load_brief(slug)
        profile = load_profile()
        return {
            "slug": slug,
            "title": brief.title if brief else slug,
            "kind": brief.kind if brief else "report",
            "cursor": meta.get("cursor") or "",
            "outline": outline,
            "sections": sections,
            "literature": literature,
            "profile": profile_to_prompt(profile),
            "profile_data": {
                "language": profile.language,
                "tone": profile.tone,
                "structure": profile.structure,
                "citation": profile.citation,
                "rejects": list(profile.rejects),
            },
            "skills": self.list_skills(),
            "pending_confirmation": self.pending_confirmation,
        }

    def export_word(self, project_slug: str | None = None) -> dict:
        """导出 / 重写 export.docx，返回路径。"""
        slug = (project_slug or self.current_project or "").strip()
        if not slug:
            return {"ok": False, "error": "请先选择项目"}
        try:
            path = export_docx(slug)
        except FileNotFoundError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"导出失败: {exc}"}
        return {"ok": True, "path": str(path.resolve())}

    def attach_file(self, project_slug: str, source_path: str) -> dict:
        """
        附件骨架：.docx → template.docx；其它 → 待确认 user_file 文献。

        TODO: 弹出文献确认卡、PDF 抽文本失败时拒绝 accepted。
        """
        slug = (project_slug or self.current_project or "").strip()
        if not slug:
            return {"ok": False, "error": "请先选择项目"}
        src = Path(source_path)
        if not src.is_file():
            return {"ok": False, "error": f"文件不存在: {source_path}"}

        root = store.project_dir(slug)
        root.mkdir(parents=True, exist_ok=True)
        suffix = src.suffix.lower()

        if suffix == ".docx":
            dest = root / "template.docx"
            shutil.copy2(src, dest)
            # 骨架：记下可从模板抽大纲，真正提议仍走 update_outline 确认卡
            suggested = suggest_outline(slug)
            return {
                "ok": True,
                "kind": "template",
                "path": str(dest),
                "suggested_outline": suggested,
                "message": "已保存为 template.docx",
            }

        # 其它文件：登记为 user_file 候选（先直接 accepted 骨架，确认卡流程 TODO）
        lit_id = f"local-{_slugify_title(src.stem) or 'file'}"
        dest_dir = root / "uploads"
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        store.append_literature(
            slug,
            Literature(
                id=lit_id,
                title=src.stem,
                status="accepted",
                content_source="user_file",
                local_path=str(dest),
            ),
        )
        return {
            "ok": True,
            "kind": "user_file",
            "literature_id": lit_id,
            "path": str(dest),
            "message": "已登记本地材料（确认卡与抽文本 TODO）",
        }

    # ---------- 对话 / 确认 ----------

    def send_message(
        self,
        message: str,
        project_slug: str,
        context: dict | None = None,
    ) -> dict:
        """
        发送用户消息，invoke 一轮图。

        context 骨架字段：
          - section_id: 右栏点选的修订目标
          - 将来可扩 attach / 快捷语法解析结果
        """
        text = (message or "").strip()
        slug = (project_slug or "").strip()
        ctx = dict(context or {})
        if not slug:
            return {"type": "message", "content": "请先选择项目"}
        if not text:
            return {"type": "message", "content": "消息不能为空"}

        root = store.project_dir(slug)
        if not root.is_dir():
            return {"type": "message", "content": f"项目不存在: {slug}"}

        self._ensure_graph(slug)
        self._sync_pending_from_checkpoint()
        if not self._graph:
            return {"type": "message", "content": "图未初始化"}

        if self.pending_confirmation:
            card_type = self.pending_confirmation.get("card_type")
            if card_type == "question":
                return self.confirm_action(True, {"text": text})
            return {
                "type": "confirmation",
                "data": self.pending_confirmation,
                "content": "请先处理当前确认卡",
            }

        meta = store.load_meta(slug)
        cursor = meta.get("cursor") or ""
        section_id = (ctx.get("section_id") or "").strip()
        text, parsed_section = _parse_section_shortcut(text, meta.get("sections") or [])
        if parsed_section:
            section_id = parsed_section
        if section_id:
            cursor = section_id

        # 骨架：把修订目标写进 user_input 前缀，供模型/节点看见
        user_input = text
        if section_id:
            title = next(
                (
                    s.get("title")
                    for s in (meta.get("sections") or [])
                    if s.get("id") == section_id
                ),
                section_id,
            )
            user_input = f"【修订目标: {title} (id={section_id})】\n{text}"

        last_observation = self._last_observation_from_checkpoint()
        self.file_snapshots = capture_file_snapshots(slug)

        try:
            result = self._graph.invoke(
                {
                    "project_slug": slug,
                    "cursor": cursor,
                    "user_input": user_input,
                    "last_observation": last_observation,
                    "file_snapshots": self.file_snapshots,
                },
                self._thread_config(),
            )
        except Exception as exc:  # noqa: BLE001
            return {"type": "message", "content": f"运行失败: {exc}"}

        return self._response_from_result(result, done_type="message")

    def confirm_action(self, accept: bool, payload: dict | None = None) -> dict:
        if not self.pending_confirmation:
            return {"type": "message", "content": "没有待确认的动作"}
        if not self._graph or not self.current_project:
            return {"type": "message", "content": "没有打开的项目"}

        extra = dict(payload or {})
        resolution = (extra.pop("conflict_resolution", None) or "").strip()

        conflict = build_conflict_report(
            self.current_project,
            self.file_snapshots,
            pending_confirmation=self.pending_confirmation,
        )
        if conflict and resolution not in ("keep_disk", "proceed"):
            if resolution == "abort":
                return {
                    "type": "confirmation",
                    "data": self.pending_confirmation,
                    "content": "已取消确认，文稿保持磁盘现状",
                }
            # 未选择如何处理冲突：把冲突卡交给窗口
            return {"type": "conflict", "data": conflict}

        if conflict and resolution in ("keep_disk", "proceed"):
            # 以当前磁盘为准，刷新快照后再 resume
            self.file_snapshots = capture_file_snapshots(self.current_project)

        resume = self._build_resume_payload(bool(accept), extra)
        card = self.pending_confirmation
        self.pending_confirmation = None

        try:
            result = self._graph.invoke(Command(resume=resume), self._thread_config())
        except Exception as exc:  # noqa: BLE001
            self.pending_confirmation = card
            return {"type": "message", "content": f"确认失败: {exc}"}

        self.file_snapshots = capture_file_snapshots(self.current_project)
        return self._response_from_result(result, done_type="update")

    # ---------- 画像 / skill 管理骨架 ----------

    def list_skills(self) -> list[dict]:
        """列出内置 + 用户 skill（名称、description、是否内置）。"""
        catalog = scan_skills()
        items = []
        for name, skill in sorted(catalog.items()):
            items.append(
                {
                    "name": name,
                    "description": skill.get("description") or "",
                    "is_builtin": bool(skill.get("is_builtin")),
                }
            )
        return items

    def delete_skill(self, name: str) -> dict:
        """删除 skills_user/<name>/；内置不可删。"""
        name = (name or "").strip()
        catalog = scan_skills()
        skill = catalog.get(name)
        if skill is None:
            return {"ok": False, "error": f"未找到 skill: {name}"}
        if skill.get("is_builtin"):
            return {"ok": False, "error": "不能删除内置 skill"}
        path = Path("skills_user") / name
        if path.is_dir():
            shutil.rmtree(path)
        return {"ok": True, "name": name}

    def update_skill_description(self, name: str, description: str) -> dict:
        """
        直接改用户 skill 的 description（不经模型）。

        TODO: 保留正文、只改 frontmatter。
        """
        name = (name or "").strip()
        catalog = scan_skills()
        skill = catalog.get(name)
        if skill is None:
            return {"ok": False, "error": f"未找到 skill: {name}"}
        if skill.get("is_builtin"):
            return {"ok": False, "error": "不能改内置 skill"}
        path = Path(skill["path"])
        # 骨架：整文件重写 frontmatter + 原 body 尽量保留
        from deepdocument.utils import format_frontmatter, parse_frontmatter

        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        meta = dict(meta or {})
        meta["name"] = name
        meta["description"] = description
        path.write_text(format_frontmatter(meta, body), encoding="utf-8")
        return {"ok": True, "name": name}

    def delete_profile_reject(self, index: int) -> dict:
        """删除画像 rejects 列表中的一项。"""
        profile = load_profile()
        if index < 0 or index >= len(profile.rejects):
            return {"ok": False, "error": "索引无效"}
        profile.rejects.pop(index)
        save_profile(profile)
        return {"ok": True, "profile": profile_to_prompt()}

    # ---------- 内部 ----------

    def _sync_pending_from_checkpoint(self) -> None:
        if not self._graph or not self.current_project:
            return
        try:
            snapshot = self._graph.get_state(self._thread_config())
        except Exception:  # noqa: BLE001
            return
        for task in getattr(snapshot, "tasks", ()) or ():
            interrupts = getattr(task, "interrupts", None) or ()
            if not interrupts:
                continue
            value = getattr(interrupts[0], "value", None)
            if isinstance(value, dict):
                self.pending_confirmation = value
                return

    def _last_observation_from_checkpoint(self) -> str:
        if not self._graph or not self.current_project:
            return ""
        try:
            snapshot = self._graph.get_state(self._thread_config())
        except Exception:  # noqa: BLE001
            return ""
        values = getattr(snapshot, "values", None) or {}
        return str(values.get("last_observation") or "")

    def _build_resume_payload(self, accept: bool, payload: dict | None) -> dict:
        extra = dict(payload or {})
        card = self.pending_confirmation or {}
        card_type = card.get("card_type")
        resume: dict[str, Any] = {"accept": accept}

        if card_type == "literature":
            if "selected_ids" in extra:
                resume["selected_ids"] = list(extra.get("selected_ids") or [])
            elif accept:
                resume["selected_ids"] = [
                    item.get("id")
                    for item in (card.get("items") or [])
                    if item.get("id") and item.get("available", True)
                ]
            else:
                resume["selected_ids"] = []
        elif card_type == "outline":
            if "titles" in extra:
                resume["titles"] = list(extra.get("titles") or [])
            elif card.get("titles"):
                resume["titles"] = list(card["titles"])
        elif card_type == "skill":
            if extra.get("markdown"):
                resume["markdown"] = extra["markdown"]
            elif card.get("markdown"):
                resume["markdown"] = card["markdown"]
            if extra.get("name"):
                resume["name"] = extra["name"]
            elif card.get("name"):
                resume["name"] = card["name"]
        elif card_type == "question":
            text = extra.get("text") or extra.get("answer") or ""
            resume["text"] = text
            resume["answer"] = text

        return resume

    def _response_from_result(self, result: Any, *, done_type: str = "update") -> dict:
        card = _interrupt_value(result)
        if card is not None:
            self.pending_confirmation = card
            if self.current_project:
                self.file_snapshots = capture_file_snapshots(self.current_project)
            return {"type": "confirmation", "data": card}

        observation = ""
        if isinstance(result, dict):
            observation = str(result.get("last_observation") or "").strip()
        return {
            "type": done_type,
            "content": observation or ("已更新" if done_type == "update" else "本轮完成"),
        }


def _interrupt_value(result: Any) -> dict | None:
    if not isinstance(result, dict):
        return None
    interrupts = result.get("__interrupt__") or []
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", None)
    if value is None and isinstance(first, dict):
        value = first.get("value")
    return value if isinstance(value, dict) else None


def _slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)
    if re.fullmatch(r"[\u4e00-\u9fff\-]+", slug or ""):
        # 纯中文题目用拼音式 slug 太重；骨架用 hash 短码
        digest = abs(hash(title)) % 10_000_000
        return f"doc-{digest}"
    return (slug or "project")[:48]


def _parse_section_shortcut(
    text: str,
    sections: list[dict],
) -> tuple[str, str | None]:
    """
    快捷语法骨架：「改第 3 节:…」→ (余下正文, section_id)

    TODO: 支持「改 总结:」按标题匹配。
    """
    match = re.match(r"^改第\s*(\d+)\s*节\s*[:：]\s*(.*)$", text, flags=re.DOTALL)
    if not match:
        return text, None
    index = int(match.group(1)) - 1
    rest = (match.group(2) or "").strip() or text
    if 0 <= index < len(sections):
        return rest, str(sections[index].get("id") or "")
    return text, None
