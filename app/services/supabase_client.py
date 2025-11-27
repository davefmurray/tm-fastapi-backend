"""
Supabase Client

Fetches JWT tokens and shop ID from Supabase (auto-refreshed by Chrome extension).
"""

import os
from supabase import create_client, Client
from typing import Optional, Tuple
from datetime import datetime


class SupabaseTokenManager:
    """Manages JWT token retrieval from Supabase"""

    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.table_name = os.getenv("SUPABASE_TABLE_NAME", "jwt_tokens")

    async def get_latest_token(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get latest JWT token and shop ID from Supabase

        Returns:
            Tuple of (jwt_token, shop_id)
        """
        try:
            # Query for latest token
            result = self.supabase.table(self.table_name) \
                .select("jwt_token, shop_id, updated_at") \
                .order("updated_at", desc=True) \
                .limit(1) \
                .execute()

            if result.data and len(result.data) > 0:
                token_data = result.data[0]
                jwt_token = token_data.get("jwt_token")
                shop_id = str(token_data.get("shop_id"))
                updated_at = token_data.get("updated_at")

                print(f"[Supabase] Retrieved token (updated: {updated_at})")

                return jwt_token, shop_id
            else:
                print("[Supabase] No tokens found in database")
                return None, None

        except Exception as e:
            print(f"[Supabase] Error fetching token: {e}")
            return None, None

    async def update_token(self, jwt_token: str, shop_id: str) -> bool:
        """
        Update/insert token in Supabase

        Returns:
            True if successful
        """
        try:
            # Upsert token - update if shop_id exists, insert if not
            result = self.supabase.table(self.table_name) \
                .upsert({
                    "shop_id": int(shop_id),
                    "jwt_token": jwt_token,
                    "updated_at": datetime.utcnow().isoformat()
                }, on_conflict="shop_id") \
                .execute()

            print(f"[Supabase] Token updated for shop {shop_id}")
            return True

        except Exception as e:
            print(f"[Supabase] Error updating token: {e}")
            return False

    async def get_token_with_fallback(self) -> Tuple[str, str]:
        """
        Get token from Supabase with fallback to environment variables

        Returns:
            Tuple of (jwt_token, shop_id)
        Raises:
            ValueError if no token found
        """
        # Try Supabase first
        jwt_token, shop_id = await self.get_latest_token()

        # Fallback to environment variables
        if not jwt_token:
            jwt_token = os.getenv("TM_AUTH_TOKEN")
            shop_id = os.getenv("TM_SHOP_ID")

            if jwt_token:
                print("[Fallback] Using token from environment variables")

        if not jwt_token or not shop_id:
            raise ValueError(
                "No JWT token found in Supabase or environment variables. "
                "Make sure Chrome extension is running or TM_AUTH_TOKEN is set."
            )

        return jwt_token, shop_id


# Singleton instance
_token_manager: Optional[SupabaseTokenManager] = None


def get_token_manager() -> SupabaseTokenManager:
    """Get or create Supabase token manager"""
    global _token_manager
    if _token_manager is None:
        _token_manager = SupabaseTokenManager()
    return _token_manager
