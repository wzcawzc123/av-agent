"""桌面版 API 客户端（同步 httpx，直连本机 FastAPI）。

本机回环（127.0.0.1）请求免口令，因此无需携带 token。
所有方法返回解析后的 JSON（dict/list）；请求失败抛 ApiError。
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = os.environ.get("AV_BASE_URL", "http://127.0.0.1:8000")


class ApiError(Exception):
    """后端返回错误或网络不可达。message 面向用户展示。"""

    def __init__(self, message: str, status: int = 0, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail


class AvApi:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    # ---------- 基础请求 ----------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise ApiError(f"无法连接本地服务：{e}") from e
        if resp.status_code >= 400:
            detail = ""
            try:
                payload = resp.json()
                if isinstance(payload, dict) and "detail" in payload:
                    detail = str(payload["detail"])
            except Exception:
                detail = resp.text[:200]
            raise ApiError(detail or f"请求失败（HTTP {resp.status_code}）",
                           status=resp.status_code)
        if not resp.content:
            return None
        return resp.json()

    def _get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params={k: v for k, v in params.items() if v not in (None, "")})

    def _post(self, path: str, json_body: Any = None, **params: Any) -> Any:
        kwargs: dict[str, Any] = {}
        if json_body is not None:
            kwargs["json"] = json_body
        if params:
            kwargs["params"] = {k: v for k, v in params.items() if v not in (None, "")}
        return self._request("POST", path, **kwargs)

    def _put(self, path: str, json_body: Any = None, **params: Any) -> Any:
        kwargs: dict[str, Any] = {}
        if json_body is not None:
            kwargs["json"] = json_body
        if params:
            kwargs["params"] = params
        return self._request("PUT", path, **kwargs)

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ---------- 健康 / 对话 / 生成 ----------

    def health(self) -> dict:
        return self._get("/api/health")

    def chat(self, text: str, project_id: Optional[int] = None) -> dict:
        body: dict[str, Any] = {"text": text}
        if project_id is not None:
            body["project_id"] = project_id
        return self._post("/api/chat", json_body=body)

    def agent_chat(self, text: str, project_id: Optional[int] = None) -> dict:
        """Agent 模式：模型可自主调用工具完成需求。"""
        body: dict[str, Any] = {"text": text}
        if project_id is not None:
            body["project_id"] = project_id
        return self._post("/api/agent/chat", json_body=body)

    def generate(self, project_id: int) -> dict:
        return self._post("/api/generate", json_body={"project_id": project_id})

    def download(self, path: str, save_to: str) -> str:
        """下载生成文件到本地目录，返回保存路径。"""
        try:
            resp = self._client.get("/api/download", params={"path": path})
        except httpx.HTTPError as e:
            raise ApiError(f"下载失败：{e}") from e
        if resp.status_code >= 400:
            raise ApiError(f"下载失败（HTTP {resp.status_code}）", status=resp.status_code)
        os.makedirs(os.path.dirname(save_to) or ".", exist_ok=True)
        with open(save_to, "wb") as f:
            f.write(resp.content)
        return save_to

    def run_engine(self, engine: str, payload: dict) -> dict:
        """直接运行工具引擎（deviation/meeting/broadcast/led），返回 {"file": ...}。"""
        return self._post(f"/api/engines/{engine}", json_body=payload)

    def led_specs(self) -> dict:
        """可选 LED 屏体/模组型号。"""
        return self._get("/api/engines/led/specs")

    # ---------- 项目 ----------

    def list_projects(self) -> list[dict]:
        return self._get("/api/projects")

    def create_project(self, name: str) -> dict:
        return self._post("/api/projects", json_body={"name": name, "requirement_json": "{}"})

    def get_project(self, project_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}")

    def delete_project(self, project_id: int) -> dict:
        return self._delete(f"/api/projects/{project_id}")

    def project_files(self, project_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}/files")

    def project_messages(self, project_id: int) -> list[dict]:
        return self._get(f"/api/projects/{project_id}/messages")

    def project_bom(self, project_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}/bom")

    def rebuild_bom(self, project_id: int, rows: list | None = None) -> dict:
        """BOM 直出 Excel（免 LLM）。rows 为编辑后的完整 BOM 行列表。"""
        body: dict[str, Any] = {}
        if rows is not None:
            body["rows"] = rows
        return self._post(f"/api/projects/{project_id}/rebuild", json_body=body)

    def project_solutions(self, project_id: int) -> list[dict]:
        return self._get(f"/api/projects/{project_id}/solutions")

    def project_quotations(self, project_id: int) -> list[dict]:
        return self._get(f"/api/projects/{project_id}/quotations")

    # ---------- 产品库 ----------

    def list_products(self, q: str = "", brand: str = "", category: str = "") -> list[dict]:
        return self._get("/api/products", q=q, brand=brand, category=category)

    def products_match(self, q: str, limit: int = 8) -> dict:
        """参数智能匹配：自然语言 → top-k（带分数与理由）。"""
        return self._get("/api/products/match", q=q, limit=limit)

    def upload_products(self, file_path: str) -> dict:
        with open(file_path, "rb") as f:
            try:
                resp = self._client.post(
                    "/api/products",
                    files={"file": (os.path.basename(file_path), f)},
                )
            except httpx.HTTPError as e:
                raise ApiError(f"上传失败：{e}") from e
        if resp.status_code >= 400:
            raise ApiError(resp.text[:200], status=resp.status_code)
        return resp.json()

    def ingest_file(self, file_path: str, target: str = "auto") -> dict:
        """LLM 智能入库：上传任意文件，自动识别并写入产品库/知识库。"""
        with open(file_path, "rb") as f:
            try:
                resp = self._client.post(
                    "/api/ingest",
                    files={"file": (os.path.basename(file_path), f)},
                    data={"target": target},
                )
            except httpx.HTTPError as e:
                raise ApiError(f"上传失败：{e}") from e
        if resp.status_code >= 400:
            raise ApiError(resp.text[:200], status=resp.status_code)
        return resp.json()

    def update_product_price(self, product_id: int, base_price: float, market_price: float) -> dict:
        return self._post(
            f"/api/products/{product_id}/price",
            json_body={"base_price": base_price, "market_price": market_price},
        )

    def delete_product(self, product_id: int) -> dict:
        return self._delete(f"/api/products/{product_id}")

    # ---------- 模板库 ----------

    def list_templates(self) -> list[dict]:
        return self._get("/api/templates")

    def templates_doc_match(self, scene: str = "", brand: str = "") -> dict:
        """按 场景×品牌 匹配 doc/ppt 模板。"""
        return self._get("/api/templates/doc-match", scene=scene, brand=brand)

    def upload_template(self, file_path: str, description: str = "") -> dict:
        with open(file_path, "rb") as f:
            try:
                resp = self._client.post(
                    "/api/templates/upload",
                    files={"file": (os.path.basename(file_path), f)},
                    data={"description": description},
                )
            except httpx.HTTPError as e:
                raise ApiError(f"上传失败：{e}") from e
        if resp.status_code >= 400:
            raise ApiError(resp.text[:200], status=resp.status_code)
        return resp.json()

    def delete_template(self, template_id: int) -> dict:
        return self._delete(f"/api/templates/{template_id}")

    def save_bom_template(self, name: str, scene: str = "", rows: list | None = None) -> dict:
        body = {"name": name, "scene": scene, "rows": rows or []}
        return self._post("/api/templates/from-bom", json_body=body)

    # ---------- 模型 / 提供商 ----------

    def get_model_config(self) -> dict:
        return self._get("/api/settings/model")

    def put_model_config(self, provider: str, api_key: str = "", model: str = "", base_url: str = "") -> dict:
        return self._put(
            "/api/settings/model",
            json_body={"provider": provider, "api_key": api_key, "model": model, "base_url": base_url},
        )

    def list_providers(self) -> list[dict]:
        return self._get("/api/providers")

    def create_provider(self, provider: dict) -> dict:
        return self._post("/api/providers", json_body=provider)

    def delete_provider(self, provider_id: str) -> dict:
        return self._delete(f"/api/providers/{provider_id}")

    def copy_provider(self, provider_id: str) -> dict:
        return self._post(f"/api/providers/{provider_id}/copy")

    def reset_provider(self, provider_id: str) -> dict:
        return self._post(f"/api/providers/{provider_id}/reset")

    def fetch_provider_models(self, provider_id: str) -> dict:
        return self._post(f"/api/providers/{provider_id}/fetch-models")

    def test_provider(self, provider_id: str) -> dict:
        return self._post(f"/api/providers/{provider_id}/test")

    # ---------- 招标改单 ----------

    def upload_tender(self, file_path: str, project_id: int = 0) -> dict:
        with open(file_path, "rb") as f:
            try:
                resp = self._client.post(
                    "/api/tender/upload",
                    files={"file": (os.path.basename(file_path), f)},
                    data={"project_id": str(project_id)},
                )
            except httpx.HTTPError as e:
                raise ApiError(f"上传失败：{e}") from e
        if resp.status_code >= 400:
            raise ApiError(resp.text[:200], status=resp.status_code)
        return resp.json()

    def tender_snapshots(self, project_id: int) -> dict:
        return self._get(f"/api/tender/{project_id}/snapshots")

    def tender_snapshot(self, project_id: int, snapshot: str) -> dict:
        return self._get(f"/api/tender/{project_id}/snapshots/{snapshot}")

    def tender_edit_row(self, project_id: int, source_idx: int, **fields: str) -> dict:
        body = {k: v for k, v in fields.items() if v}
        return self._put(f"/api/tender/{project_id}/rows/{source_idx}", json_body=body)

    def tender_confirm(self, project_id: int, snapshot: str) -> dict:
        return self._post(
            f"/api/tender/{project_id}/confirm",
            json_body={"project_id": project_id, "snapshot": snapshot},
        )

    # ---------- 知识库 / 工作流 ----------

    def list_knowledge(self) -> dict:
        return self._get("/api/knowledge")

    def register_knowledge(self, title: str, doc_type: str, file_path: str = "",
                           excerpt: str = "", meta: str = "") -> dict:
        body = {"title": title, "doc_type": doc_type, "file_path": file_path,
                "excerpt": excerpt, "meta": meta}
        return self._post("/api/knowledge", json_body=body)

    def delete_knowledge(self, doc_id: int) -> dict:
        return self._delete(f"/api/knowledge/{doc_id}")

    # ---------- 更新检查 ----------

    def update_check(self) -> dict:
        return self._get("/api/update/check")

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
