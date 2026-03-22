from src.config import settings
import httpx
from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional, Dict, Any
import asyncio
from src.utils.logger import get_logger

logger = get_logger()


class JupyterService:
    """
    Manages communication with the Jupyter Server running in the sidecar container.
    Handles proxying of HTTP requests and WebSocket connections.
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url or settings.jupyter.base_url
        self.token = token or settings.jupyter.token

        if not self.token:
            logger.warning(
                "JUPYTER_TOKEN is not configured. Jupyter features will be disabled."
            )

        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}

    async def get_status(self) -> Dict[str, Any]:
        """Check if Jupyter server is reachable."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/status", headers=self.headers
                )
                return response.json()
            except Exception as e:
                logger.error(f"Failed to connect to Jupyter: {e}")
                return {"status": "unreachable", "error": str(e)}

    async def create_kernel(self) -> str:
        """Create a new Python 3 kernel and return its ID."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/kernels",
                    headers=self.headers,
                    json={"name": "python3"},
                )
                response.raise_for_status()
                data = response.json()
                kernel_id = data["id"]
                logger.info(f"Created new Jupyter kernel: {kernel_id}")
                return kernel_id
            except Exception as e:
                logger.error(f"Failed to create kernel: {e}")
                raise

    async def proxy_request(
        self, method: str, path: str, body: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Proxy a generic HTTP request to Jupyter."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/{path.lstrip('/')}"
            try:
                response = await client.request(
                    method, url, headers=self.headers, json=body
                )
                return response.json()
            except Exception as e:
                logger.error(f"Proxy request failed: {e}")
                raise

    async def proxy_websocket(self, websocket: WebSocket, kernel_id: str):
        """
        Proxy a WebSocket connection from the frontend to the Jupyter kernel.
        """
        await websocket.accept()

        jupyter_ws_url = f"{self.base_url.replace('http', 'ws')}/api/kernels/{kernel_id}/channels?token={self.token}"

        if True:  # Used just for initial handshake/headers setup if needed, but for WS using websockets
            # Note: httpx doesn't support WS directly in the standard client same way.
            # We will use 'websockets' library or 'httpx_ws' if available.
            # For simplicity, implementing a manual loop with 'aiohttp' or similar is common,
            # but let's use the standard 'websockets' library approach or just raw socket transfer.
            # Ideally, we should use a library like 'websockets' to connect to upstream.

            # Since we can't easily add new dependencies without user approval,
            # we will try to use `httpx` if it has WS support installed, or fallback to detailed implementation.
            # Assuming 'websockets' might not be in the plain docker image unless we added it.
            # Reviewing requirements... 'websockets' is often standard.

            from websockets.client import connect as ws_connect  # type: ignore

            try:
                async with ws_connect(jupyter_ws_url) as jupyter_ws:

                    async def forward_client_to_jupyter():
                        try:
                            while True:
                                data = await websocket.receive_text()
                                await jupyter_ws.send(data)
                        except WebSocketDisconnect:
                            logger.info("Client disconnected")
                        except Exception as e:
                            logger.error(f"Error forwarding to Jupyter: {e}")

                    async def forward_jupyter_to_client():
                        try:
                            async for message in jupyter_ws:
                                await websocket.send_text(message)
                        except Exception as e:
                            logger.error(f"Error forwarding to Client: {e}")

                    await asyncio.gather(
                        forward_client_to_jupyter(), forward_jupyter_to_client()
                    )
            except Exception as e:
                logger.error(f"WebSocket proxy error: {e}")
                await websocket.close(code=1011)


jupyter_service = JupyterService()
