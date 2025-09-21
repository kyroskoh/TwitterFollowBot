"""
X API v2 Authentication with OAuth 2.0 support.
"""

import base64
import hashlib
import secrets
import urllib.parse
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

import tweepy
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


class TokenResponse(BaseModel):
    """OAuth 2.0 Token Response model."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if not self.expires_in:
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.expires_in)
        return datetime.utcnow() >= expiry_time


@dataclass
class PKCEChallenge:
    """PKCE Challenge for OAuth 2.0 Authorization Code Flow."""
    
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"
    
    @classmethod
    def generate(cls) -> "PKCEChallenge":
        """Generate a new PKCE challenge."""
        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return cls(
            code_verifier=code_verifier,
            code_challenge=code_challenge
        )


class XAuth:
    """X API v2 Authentication handler with OAuth 2.0 support."""
    
    # X API v2 OAuth 2.0 endpoints
    AUTHORIZATION_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    REVOKE_URL = "https://api.twitter.com/2/oauth2/revoke"
    
    # Default scopes for bot functionality
    DEFAULT_SCOPES = [
        "tweet.read",
        "tweet.write", 
        "users.read",
        "follows.read",
        "follows.write",
        "like.read",
        "like.write",
        "list.read",
        "list.write",
        "mute.read",
        "mute.write",
        "offline.access"  # For refresh tokens
    ]
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080/callback",
        scopes: Optional[list[str]] = None
    ):
        """
        Initialize X API authentication.
        
        Args:
            client_id: X API v2 Client ID
            client_secret: X API v2 Client Secret  
            redirect_uri: OAuth 2.0 redirect URI
            scopes: List of OAuth 2.0 scopes
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or self.DEFAULT_SCOPES
        self.current_token: Optional[TokenResponse] = None
        self._pkce_challenge: Optional[PKCEChallenge] = None
        
        logger.info("X Auth initialized", client_id=client_id[:8] + "...")
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate OAuth 2.0 authorization URL with PKCE.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Tuple of (authorization_url, state)
        """
        # Generate PKCE challenge
        self._pkce_challenge = PKCEChallenge.generate()
        
        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge": self._pkce_challenge.code_challenge,
            "code_challenge_method": self._pkce_challenge.code_challenge_method
        }
        
        auth_url = f"{self.AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}"
        
        logger.info("Generated authorization URL", state=state)
        return auth_url, state
    
    async def exchange_code_for_token(self, authorization_code: str) -> TokenResponse:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Authorization code from callback
            
        Returns:
            TokenResponse with access and refresh tokens
        """
        if not self._pkce_challenge:
            raise ValueError("No PKCE challenge available. Call get_authorization_url first.")
        
        import httpx
        
        # Prepare token request
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": self._pkce_challenge.code_verifier,
            "client_id": self.client_id,
        }
        
        # Create Basic Auth header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=token_data,
                headers=headers
            )
            response.raise_for_status()
            token_data = response.json()
        
        # Create token response
        self.current_token = TokenResponse(**token_data)
        
        logger.info("Successfully exchanged code for tokens",
                   has_refresh_token=bool(self.current_token.refresh_token))
        
        return self.current_token
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token from previous auth
            
        Returns:
            New TokenResponse with fresh access token
        """
        import httpx
        
        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        
        # Create Basic Auth header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=token_data,
                headers=headers
            )
            response.raise_for_status()
            new_token_data = response.json()
        
        # Create new token response
        self.current_token = TokenResponse(**new_token_data)
        
        logger.info("Successfully refreshed access token")
        return self.current_token
    
    async def revoke_token(self, token: str, token_type: str = "access_token") -> None:
        """
        Revoke an access or refresh token.
        
        Args:
            token: Token to revoke
            token_type: Type of token ("access_token" or "refresh_token")
        """
        import httpx
        
        revoke_data = {
            "token": token,
            "token_type_hint": token_type,
            "client_id": self.client_id,
        }
        
        # Create Basic Auth header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.REVOKE_URL,
                data=revoke_data,
                headers=headers
            )
            response.raise_for_status()
        
        logger.info("Successfully revoked token", token_type=token_type)
    
    def get_tweepy_client(self, bearer_token: Optional[str] = None) -> tweepy.Client:
        """
        Create a Tweepy client for API calls.
        
        Args:
            bearer_token: Optional bearer token for app-only auth
            
        Returns:
            Configured Tweepy client
        """
        if bearer_token:
            # App-only authentication
            return tweepy.Client(bearer_token=bearer_token)
        
        if not self.current_token:
            raise ValueError("No access token available. Complete OAuth flow first.")
        
        # User context authentication
        return tweepy.Client(
            bearer_token=self.current_token.access_token,
            wait_on_rate_limit=True
        )
    
    def is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        if not self.current_token:
            return False
        
        return not self.current_token.is_expired
    
    def to_dict(self) -> Dict[str, Any]:
        """Export authentication state to dictionary."""
        if not self.current_token:
            return {}
        
        return {
            "access_token": self.current_token.access_token,
            "token_type": self.current_token.token_type,
            "expires_in": self.current_token.expires_in,
            "refresh_token": self.current_token.refresh_token,
            "scope": self.current_token.scope,
            "created_at": self.current_token.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080/callback"
    ) -> "XAuth":
        """Create XAuth instance from saved authentication data."""
        auth = cls(client_id, client_secret, redirect_uri)
        
        if data:
            # Parse datetime
            created_at = datetime.fromisoformat(data["created_at"])
            data["created_at"] = created_at
            
            auth.current_token = TokenResponse(**data)
        
        return auth