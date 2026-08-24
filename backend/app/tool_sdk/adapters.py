from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.tool_sdk.errors import (
    IntegrationNotConfiguredError,
    IntegrationUnavailableError,
    RateLimitedError,
    UnsafeOperationError,
)


class IntegrationAdapter(ABC):
    provider: str

    @abstractmethod
    async def verify(self) -> dict: ...


class HTTPAdapter(IntegrationAdapter):
    def __init__(self, provider, base_url=None, token=None, timeout=20):
        self.provider = provider
        self.base_url = (base_url or "").rstrip("/")
        self._token = token
        self.timeout = timeout
        if self.base_url:
            self._validate_url(self.base_url)

    @staticmethod
    def _validate_url(url):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not host
            or host in {"localhost", "127.0.0.1", "::1"}
            or host.endswith(".local")
        ):
            raise UnsafeOperationError(
                "Integration URLs must use HTTPS and a public approved host"
            )

    async def request(self, method, path, *, params=None):
        if not self.base_url or not self._token:
            raise IntegrationNotConfiguredError(f"{self.provider} is not configured")
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, follow_redirects=False
            ) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/json",
                    },
                )
            if response.status_code == 429:
                raise RateLimitedError(f"{self.provider} rate limit reached")
            if response.status_code >= 500:
                raise IntegrationUnavailableError(
                    f"{self.provider} is temporarily unavailable"
                )
            if response.status_code >= 400:
                raise IntegrationUnavailableError(
                    f"{self.provider} rejected the request"
                )
            if method.upper() == "HEAD":
                data = {
                    "content_type": response.headers.get("content-type"),
                    "content_length": response.headers.get("content-length"),
                    "etag": response.headers.get("etag"),
                    "last_modified": response.headers.get("last-modified"),
                }
            else:
                try:
                    data = response.json()
                except ValueError:
                    data = {"content": response.text[:1_000_000]}
            return data, response.headers.get("x-request-id") or response.headers.get(
                "x-ms-request-id"
            )
        except httpx.HTTPError as exc:
            raise IntegrationUnavailableError(
                f"Could not reach {self.provider}"
            ) from exc

    async def verify(self):
        try:
            await self.request("GET", "/")
            return {"ready": True, "message": "Connection verified"}
        except Exception as exc:  # noqa: BLE001 -- readiness reports adapter-specific failures as data
            return {"ready": False, "message": getattr(exc, "safe_message", str(exc))}


class ServiceNowAdapter(HTTPAdapter):
    def __init__(self):
        super().__init__(
            "servicenow",
            os.getenv("SERVICENOW_INSTANCE_URL"),
            os.getenv("SERVICENOW_ACCESS_TOKEN"),
            int(os.getenv("SERVICENOW_TIMEOUT_SECONDS", "20")),
        )

    async def search(self, table, params):
        if table not in {"incident", "change_request", "cmdb_ci"}:
            raise UnsafeOperationError("ServiceNow table is not allowed")
        data, request_id = await self.request(
            "GET", f"/api/now/table/{table}", params=params
        )
        return data.get("result", []), request_id


class MicrosoftGraphAdapter(HTTPAdapter):
    def __init__(self):
        super().__init__(
            "microsoft_graph",
            os.getenv("MICROSOFT_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0"),
            os.getenv("MICROSOFT_GRAPH_ACCESS_TOKEN"),
        )

    async def list_files(self, site_or_drive, path):
        return await self.request(
            "GET", f"/drives/{site_or_drive}/root:/{path}:/children"
        )


class AzureBlobAdapter(HTTPAdapter):
    def __init__(self):
        super().__init__(
            "azure_blob",
            os.getenv("AZURE_BLOB_ENDPOINT"),
            os.getenv("AZURE_BLOB_ACCESS_TOKEN"),
        )

    def allowed_container(self, name):
        allowed = {
            x.strip()
            for x in os.getenv("AZURE_BLOB_ALLOWED_CONTAINERS", "").split(",")
            if x.strip()
        }
        if not allowed or name not in allowed:
            raise UnsafeOperationError("Blob container is not approved")


class AzureKeyVaultAdapter(HTTPAdapter):
    def __init__(self):
        super().__init__(
            "azure_keyvault",
            os.getenv("AZURE_KEYVAULT_URI"),
            os.getenv("AZURE_KEYVAULT_ACCESS_TOKEN"),
        )

    async def metadata(self, name=None):
        path = f"/secrets/{name}" if name else "/secrets"
        data, request_id = await self.request(
            "GET", path, params={"api-version": "7.4"}
        )

        def safe(item):
            attrs = item.get("attributes", {})
            return {
                "id": item.get("id"),
                "name": item.get("id", "").rstrip("/").split("/")[-1],
                "enabled": attrs.get("enabled"),
                "created": attrs.get("created"),
                "updated": attrs.get("updated"),
                "tags": item.get("tags", {}),
            }

        if "value" in data:
            data.pop("value", None)
        return (
            {"items": [safe(x) for x in data.get("value", [])]}
            if not name
            else safe(data)
        ), request_id


class LocalFileAdapter(IntegrationAdapter):
    provider = "local_files"

    def __init__(self, roots=None, max_bytes=None):
        configured = (
            roots if roots is not None else os.getenv("TOOL_FILE_ALLOWED_ROOTS", "")
        )
        self.roots = [
            Path(p).expanduser().resolve()
            for p in (
                configured.split(os.pathsep)
                if isinstance(configured, str)
                else configured
            )
            if p
        ]
        self.max_bytes = max_bytes or int(os.getenv("TOOL_FILE_MAX_BYTES", "1048576"))
        self.extensions = {
            x.strip().lower()
            for x in os.getenv(
                "TOOL_FILE_ALLOWED_EXTENSIONS", ".txt,.md,.json,.csv,.log,.yaml,.yml"
            ).split(",")
        }

    def resolve(self, path):
        candidate = Path(path)
        if not candidate.is_absolute() and self.roots:
            candidate = self.roots[0] / candidate
        resolved = candidate.resolve(strict=True)
        if not any(resolved == root or root in resolved.parents for root in self.roots):
            raise UnsafeOperationError("File path is outside approved roots")
        if resolved.is_symlink():
            raise UnsafeOperationError("Symbolic links are not allowed")
        return resolved

    async def verify(self):
        return {
            "ready": bool(self.roots),
            "message": f"{len(self.roots)} approved root(s)"
            if self.roots
            else "No approved roots configured",
        }

    def list(self, path=".", offset=0, limit=25):
        directory = self.resolve(path)
        items = sorted(directory.iterdir(), key=lambda p: p.name.lower())[
            offset : offset + limit
        ]
        return [
            {
                "name": p.name,
                "path": str(
                    p.relative_to(
                        next(r for r in self.roots if p == r or r in p.parents)
                    )
                ),
                "type": "directory" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else None,
                "modified_at": p.stat().st_mtime,
            }
            for p in items
            if not p.is_symlink()
        ]

    def metadata(self, path):
        p = self.resolve(path)
        s = p.stat()
        return {
            "name": p.name,
            "size": s.st_size,
            "extension": p.suffix.lower(),
            "modified_at": s.st_mtime,
            "is_directory": p.is_dir(),
        }

    def read(self, path):
        p = self.resolve(path)
        if p.suffix.lower() not in self.extensions:
            raise UnsafeOperationError("File type is not approved")
        if p.stat().st_size > self.max_bytes:
            raise UnsafeOperationError("File exceeds the configured read limit")
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise UnsafeOperationError("Only UTF-8 text files can be read") from exc
