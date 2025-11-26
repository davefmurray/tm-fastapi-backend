"""
Tekmetric API Client

Handles all HTTP requests to Tekmetric API with authentication.
"""

import os
import httpx
from typing import Optional, Dict, Any


class TekmetricClient:
    """Client for Tekmetric API requests"""

    def __init__(self, auth_token: Optional[str] = None, shop_id: Optional[str] = None):
        self.base_url = os.getenv("TM_BASE_URL", "https://shop.tekmetric.com")
        self.auth_token = auth_token or os.getenv("TM_AUTH_TOKEN")
        self.shop_id = shop_id or os.getenv("TM_SHOP_ID")
        self.timeout = 30.0

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for TM API requests"""
        return {
            "x-auth-token": self.auth_token,
            "Content-Type": "application/json",
            "accept": "application/json"
        }

    async def get(self, path: str, params: Optional[Dict] = None) -> Any:
        """Make GET request to TM API"""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, data: Dict) -> Any:
        """Make POST request to TM API"""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def put(self, path: str, data: Dict) -> Any:
        """Make PUT request to TM API"""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def patch(self, path: str, data: Dict) -> Any:
        """Make PATCH request to TM API"""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def delete(self, path: str) -> Any:
        """Make DELETE request to TM API"""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()


# Singleton instance
_tm_client: Optional[TekmetricClient] = None


def get_tm_client() -> TekmetricClient:
    """Get or create TM client instance"""
    global _tm_client
    if _tm_client is None:
        _tm_client = TekmetricClient()
    return _tm_client
