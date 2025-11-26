"""
Tekmetric API Client

Handles all HTTP requests to Tekmetric API with authentication.
Auto-fetches JWT tokens from Supabase (refreshed by Chrome extension).
"""

import os
import httpx
from typing import Optional, Dict, Any
from app.services.supabase_client import get_token_manager


class TekmetricClient:
    """Client for Tekmetric API requests"""

    def __init__(self, auth_token: Optional[str] = None, shop_id: Optional[str] = None):
        self.base_url = os.getenv("TM_BASE_URL", "https://shop.tekmetric.com")
        self.timeout = 30.0
        self.use_supabase = os.getenv("USE_SUPABASE", "true").lower() == "true"

        # Manual override if provided
        if auth_token and shop_id:
            self.auth_token = auth_token
            self.shop_id = shop_id
        else:
            # Will fetch from Supabase on first request
            self.auth_token = None
            self.shop_id = None

    async def _ensure_token(self):
        """Ensure we have a valid token (fetch from Supabase if needed)"""
        if self.auth_token and self.shop_id:
            return

        if self.use_supabase:
            try:
                token_manager = get_token_manager()
                self.auth_token, self.shop_id = await token_manager.get_token_with_fallback()
            except Exception as e:
                print(f"[TM Client] Error fetching token from Supabase: {e}")
                # Fallback to environment variables
                self.auth_token = os.getenv("TM_AUTH_TOKEN")
                self.shop_id = os.getenv("TM_SHOP_ID")
        else:
            self.auth_token = os.getenv("TM_AUTH_TOKEN")
            self.shop_id = os.getenv("TM_SHOP_ID")

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for TM API requests"""
        if not self.auth_token:
            raise ValueError("No auth token available")
        return {
            "x-auth-token": self.auth_token,
            "Content-Type": "application/json",
            "accept": "application/json"
        }

    def get_shop_id(self) -> str:
        """Get shop ID (must call _ensure_token first in async context)"""
        if not self.shop_id:
            raise ValueError("Shop ID not available - call _ensure_token first")
        return self.shop_id

    async def get(self, path: str, params: Optional[Dict] = None) -> Any:
        """Make GET request to TM API"""
        await self._ensure_token()
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, data: Dict) -> Any:
        """Make POST request to TM API"""
        await self._ensure_token()
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def put(self, path: str, data: Dict) -> Any:
        """Make PUT request to TM API"""
        await self._ensure_token()
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def patch(self, path: str, data: Dict) -> Any:
        """Make PATCH request to TM API"""
        await self._ensure_token()
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def delete(self, path: str) -> Any:
        """Make DELETE request to TM API"""
        await self._ensure_token()
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
