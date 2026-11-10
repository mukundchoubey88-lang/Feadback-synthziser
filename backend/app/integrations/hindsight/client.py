"""Official Hindsight Persistent Memory REST Client.

Provides an asynchronous HTTP client interface for Hindsight memory operations:
- Retain: POST /v1/default/banks/{bank_id}/memories
- Recall: POST /v1/default/banks/{bank_id}/memories/recall
- Reflect: POST /v1/default/banks/{bank_id}/reflect

Implements resilient timeout management, non-throwing error handling, and clean
graceful degradation when the Hindsight service is unavailable or unconfigured.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class HindsightClient:
    """Asynchronous client for interacting with Hindsight Persistent Memory REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 5.0,
        async_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = (base_url or settings.HINDSIGHT_BASE_URL or "").rstrip("/")
        self.api_key = api_key or settings.HINDSIGHT_API_KEY
        self.timeout = timeout
        self._custom_client = async_client

    @property
    def is_configured(self) -> bool:
        """Return True if base URL is populated."""
        return bool(self.base_url)

    def _get_headers(self) -> Dict[str, str]:
        """Construct authorization and content headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_client(self) -> httpx.AsyncClient:
        """Return either the injected client or a new AsyncClient instance."""
        if self._custom_client is not None:
            return self._custom_client
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=self.timeout,
        )

    async def health_check(self) -> bool:
        """Check if the Hindsight server is reachable and responding."""
        if not self.is_configured:
            return False

        try:
            if self._custom_client is not None:
                resp = await self._custom_client.get(
                    f"{self.base_url}/health",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                return resp.status_code in (200, 204, 404, 401)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/health",
                    headers=self._get_headers(),
                )
                # Any HTTP response indicates server process is alive
                return resp.status_code in (200, 204, 404, 401)
        except Exception as exc:
            logger.debug("Hindsight health check failed: %s", exc)
            return False

    async def ensure_bank(self, bank_id: str) -> bool:
        """Ensure a memory bank exists on Hindsight."""
        if not self.is_configured:
            return False

        url = f"{self.base_url}/v1/default/banks"
        payload = {"bank_id": bank_id, "name": bank_id}
        try:
            if self._custom_client is not None:
                resp = await self._custom_client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                return resp.status_code in (200, 201, 409)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )
                return resp.status_code in (200, 201, 409)
        except Exception as exc:
            logger.warning("Failed to ensure Hindsight memory bank '%s': %s", bank_id, exc)
            return False

    async def retain(
        self,
        bank_id: str,
        content: str,
        context: Optional[str] = None,
    ) -> Optional[str]:
        """Retain a new memory in the specified Hindsight bank.

        Endpoint: POST /v1/default/banks/{bank_id}/memories
        Returns the external hindsight_memory_id on success, or None on failure.
        """
        if not self.is_configured:
            logger.info("Hindsight is not configured. Retain operation skipped.")
            return None

        url = f"{self.base_url}/v1/default/banks/{bank_id}/memories"
        payload: Dict[str, Any] = {"content": content}
        if context:
            payload["context"] = context

        try:
            if self._custom_client is not None:
                resp = await self._custom_client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        url,
                        json=payload,
                        headers=self._get_headers(),
                    )

            if resp.status_code in (200, 201):
                data = resp.json()
                if isinstance(data, dict):
                    return str(
                        data.get("id")
                        or data.get("memory_id")
                        or (data.get("memory", {}).get("id") if isinstance(data.get("memory"), dict) else None)
                        or ""
                    )
                return None
            else:
                logger.warning(
                    "Hindsight retain returned HTTP %s for bank %s: %s",
                    resp.status_code,
                    bank_id,
                    resp.text[:200],
                )
                return None
        except Exception as exc:
            logger.warning("Hindsight retain failed for bank %s: %s", bank_id, exc)
            return None

    async def recall(
        self,
        bank_id: str,
        query: str,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Recall relevant memories for a query from the specified bank.

        Endpoint: POST /v1/default/banks/{bank_id}/memories/recall
        Returns dict containing 'memories' list and 'success' bool.
        """
        if not self.is_configured:
            return {
                "success": False,
                "memories": [],
                "error": "Hindsight persistent memory is not configured (HINDSIGHT_BASE_URL is unset).",
            }

        url = f"{self.base_url}/v1/default/banks/{bank_id}/memories/recall"
        payload = {"query": query, "limit": limit}

        try:
            if self._custom_client is not None:
                resp = await self._custom_client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        url,
                        json=payload,
                        headers=self._get_headers(),
                    )

            if resp.status_code == 200:
                data = resp.json()
                memories: List[Dict[str, Any]] = []
                if isinstance(data, list):
                    memories = data
                elif isinstance(data, dict):
                    memories = data.get("memories") or data.get("results") or []

                return {"success": True, "memories": memories, "error": None}
            else:
                return {
                    "success": False,
                    "memories": [],
                    "error": f"Hindsight recall returned HTTP {resp.status_code}: {resp.text[:200]}",
                }
        except Exception as exc:
            logger.warning("Hindsight recall request failed for bank %s: %s", bank_id, exc)
            return {
                "success": False,
                "memories": [],
                "error": f"Hindsight service unreachable: {str(exc)}",
            }

    async def reflect(
        self,
        bank_id: str,
        query: str,
    ) -> Dict[str, Any]:
        """Reflect and synthesize reasoning over historical memories in the specified bank.

        Endpoint: POST /v1/default/banks/{bank_id}/reflect
        Returns dict containing 'reasoning', 'memories', and 'success' bool.
        """
        if not self.is_configured:
            return {
                "success": False,
                "reasoning": None,
                "memories": [],
                "error": "Hindsight persistent memory is not configured (HINDSIGHT_BASE_URL is unset).",
            }

        url = f"{self.base_url}/v1/default/banks/{bank_id}/reflect"
        payload = {"query": query}

        try:
            if self._custom_client is not None:
                resp = await self._custom_client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        url,
                        json=payload,
                        headers=self._get_headers(),
                    )

            if resp.status_code == 200:
                data = resp.json()
                reasoning = None
                memories = []
                if isinstance(data, dict):
                    reasoning = data.get("reasoning") or data.get("reflection") or data.get("summary")
                    memories = data.get("memories") or data.get("supporting_memories") or []
                return {
                    "success": True,
                    "reasoning": reasoning,
                    "memories": memories,
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "reasoning": None,
                    "memories": [],
                    "error": f"Hindsight reflect returned HTTP {resp.status_code}: {resp.text[:200]}",
                }
        except Exception as exc:
            logger.warning("Hindsight reflect request failed for bank %s: %s", bank_id, exc)
            return {
                "success": False,
                "reasoning": None,
                "memories": [],
                "error": f"Hindsight service unreachable: {str(exc)}",
            }
