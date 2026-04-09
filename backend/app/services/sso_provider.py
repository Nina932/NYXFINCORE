"""
FinAI SSO/SAML Provider Framework
==================================
Supports multiple SSO protocols and identity providers:
  - SAML 2.0 (IdP metadata, SP entity ID, ACS URL)
  - OAuth2 / OIDC (Google Workspace, Azure AD, custom)

Each provider is configured via SSOProviderConfig and stored in the
SSOManager registry. The framework handles:
  1. SSO login initiation (redirect URL generation)
  2. Callback handling (token exchange, user attribute extraction)
  3. User creation/lookup (find-or-create from SSO attributes)
  4. JWT issuance (same tokens as local auth)

SAML XML parsing uses a lightweight stub — production deployments
should integrate python3-saml or pysaml2 for full XML signature
verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Models
# ═══════════════════════════════════════════════════════════════════════════════

class SSOProtocol(str, Enum):
    SAML2 = "saml2"
    OIDC = "oidc"
    OAUTH2 = "oauth2"


@dataclass
class SSOProviderConfig:
    """Configuration for a single SSO identity provider."""

    provider_id: str                # e.g. "google", "azure_ad", "okta"
    display_name: str               # Human-readable, e.g. "Google Workspace"
    protocol: SSOProtocol
    enabled: bool = True

    # SAML 2.0 fields
    idp_metadata_url: str = ""      # URL to IdP metadata XML
    idp_sso_url: str = ""           # IdP Single Sign-On URL (from metadata)
    idp_slo_url: str = ""           # IdP Single Logout URL
    idp_certificate: str = ""       # IdP X.509 certificate (PEM)
    sp_entity_id: str = ""          # Our SP entity ID
    sp_acs_url: str = ""            # Assertion Consumer Service URL

    # OAuth2 / OIDC fields
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    scopes: List[str] = field(default_factory=lambda: ["openid", "email", "profile"])
    redirect_uri: str = ""          # Our callback URL

    # Attribute mapping: IdP claim name -> local field name
    attribute_map: Dict[str, str] = field(default_factory=lambda: {
        "email": "email",
        "name": "full_name",
        "sub": "provider_user_id",
    })

    def to_public_dict(self) -> Dict[str, Any]:
        """Return a safe representation (no secrets)."""
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "protocol": self.protocol.value,
            "enabled": self.enabled,
            "has_client_id": bool(self.client_id),
            "has_idp_metadata": bool(self.idp_metadata_url),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Pre-built Provider Templates
# ═══════════════════════════════════════════════════════════════════════════════

def _google_workspace_config(
    client_id: str = "",
    client_secret: str = "",
    redirect_uri: str = "",
) -> SSOProviderConfig:
    """Google Workspace (G Suite) OIDC configuration."""
    return SSOProviderConfig(
        provider_id="google",
        display_name="Google Workspace",
        protocol=SSOProtocol.OIDC,
        client_id=client_id,
        client_secret=client_secret,
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=["openid", "email", "profile"],
        redirect_uri=redirect_uri,
        attribute_map={
            "email": "email",
            "name": "full_name",
            "sub": "provider_user_id",
            "picture": "avatar_url",
        },
    )


def _azure_ad_config(
    tenant_id: str = "common",
    client_id: str = "",
    client_secret: str = "",
    redirect_uri: str = "",
) -> SSOProviderConfig:
    """Azure AD / Entra ID OIDC configuration."""
    base = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"
    return SSOProviderConfig(
        provider_id="azure_ad",
        display_name="Microsoft Azure AD",
        protocol=SSOProtocol.OIDC,
        client_id=client_id,
        client_secret=client_secret,
        authorization_url=f"{base}/authorize",
        token_url=f"{base}/token",
        userinfo_url="https://graph.microsoft.com/oidc/userinfo",
        scopes=["openid", "email", "profile"],
        redirect_uri=redirect_uri,
        attribute_map={
            "email": "email",
            "name": "full_name",
            "sub": "provider_user_id",
            "preferred_username": "username",
        },
    )


def _saml2_config(
    provider_id: str = "saml_idp",
    display_name: str = "SAML Identity Provider",
    idp_metadata_url: str = "",
    idp_sso_url: str = "",
    idp_certificate: str = "",
    sp_entity_id: str = "",
    sp_acs_url: str = "",
) -> SSOProviderConfig:
    """Generic SAML 2.0 provider configuration."""
    return SSOProviderConfig(
        provider_id=provider_id,
        display_name=display_name,
        protocol=SSOProtocol.SAML2,
        idp_metadata_url=idp_metadata_url,
        idp_sso_url=idp_sso_url,
        idp_certificate=idp_certificate,
        sp_entity_id=sp_entity_id,
        sp_acs_url=sp_acs_url,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SSO State Manager (CSRF protection for OAuth flows)
# ═══════════════════════════════════════════════════════════════════════════════

class SSOStateManager:
    """In-memory nonce/state store for OAuth2 CSRF protection.

    In production, use Redis or DB-backed storage with TTL.
    """

    def __init__(self, ttl_seconds: int = 600):
        self._states: Dict[str, float] = {}  # state -> created_at
        self._ttl = ttl_seconds

    def generate(self) -> str:
        """Generate a cryptographically random state parameter."""
        self._cleanup()
        state = secrets.token_urlsafe(32)
        self._states[state] = time.time()
        return state

    def validate(self, state: str) -> bool:
        """Validate and consume a state parameter (one-time use)."""
        self._cleanup()
        created = self._states.pop(state, None)
        if created is None:
            return False
        return (time.time() - created) < self._ttl

    def _cleanup(self) -> None:
        """Remove expired states."""
        now = time.time()
        expired = [s for s, t in self._states.items() if (now - t) > self._ttl]
        for s in expired:
            self._states.pop(s, None)


# ═══════════════════════════════════════════════════════════════════════════════
# SAML 2.0 Helper (lightweight stub — production should use python3-saml)
# ═══════════════════════════════════════════════════════════════════════════════

class SAMLHelper:
    """Minimal SAML 2.0 AuthnRequest generation and response parsing.

    WARNING: This is a framework stub. It generates valid AuthnRequest URLs
    and can parse unencrypted SAML responses, but does NOT verify XML
    signatures. For production, integrate python3-saml or pysaml2.
    """

    @staticmethod
    def build_authn_request_url(config: SSOProviderConfig, relay_state: str = "") -> str:
        """Build a SAML AuthnRequest redirect URL."""
        import base64
        import zlib

        request_id = f"_finai_{secrets.token_hex(16)}"
        issue_instant = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        authn_request = (
            f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
            f'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
            f'ID="{request_id}" Version="2.0" IssueInstant="{issue_instant}" '
            f'Destination="{config.idp_sso_url}" '
            f'AssertionConsumerServiceURL="{config.sp_acs_url}" '
            f'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
            f'<saml:Issuer>{config.sp_entity_id}</saml:Issuer>'
            f'<samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" '
            f'AllowCreate="true"/>'
            f'</samlp:AuthnRequest>'
        )

        # Deflate + Base64 encode for HTTP-Redirect binding
        compressed = zlib.compress(authn_request.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(compressed).decode("utf-8")

        params = {"SAMLRequest": encoded}
        if relay_state:
            params["RelayState"] = relay_state

        return f"{config.idp_sso_url}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def parse_saml_response(saml_response_b64: str, config: SSOProviderConfig) -> Optional[Dict[str, str]]:
        """Parse a base64-encoded SAML Response and extract user attributes.

        WARNING: Does NOT verify XML signatures. Production must validate
        the signature against config.idp_certificate.

        Returns dict with extracted attributes or None on failure.
        """
        import base64
        import xml.etree.ElementTree as ET

        try:
            xml_bytes = base64.b64decode(saml_response_b64)
            xml_str = xml_bytes.decode("utf-8")

            # Define SAML namespaces
            ns = {
                "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
                "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            }

            root = ET.fromstring(xml_str)

            # Check status
            status_code = root.find(".//samlp:StatusCode", ns)
            if status_code is not None:
                status_value = status_code.get("Value", "")
                if "Success" not in status_value:
                    logger.warning("SAML response status: %s", status_value)
                    return None

            # Extract NameID (email)
            name_id = root.find(".//saml:NameID", ns)
            email = name_id.text if name_id is not None else None

            # Extract attributes from AttributeStatement
            attributes: Dict[str, str] = {}
            if email:
                attributes["email"] = email

            for attr_elem in root.findall(".//saml:Attribute", ns):
                attr_name = attr_elem.get("Name", "")
                attr_value_elem = attr_elem.find("saml:AttributeValue", ns)
                if attr_value_elem is not None and attr_value_elem.text:
                    # Map common SAML attribute names
                    friendly = attr_elem.get("FriendlyName", attr_name)
                    short_name = friendly.split("/")[-1] if "/" in friendly else friendly
                    attributes[short_name.lower()] = attr_value_elem.text

            if not attributes.get("email"):
                logger.warning("SAML response missing email attribute")
                return None

            return attributes

        except Exception as e:
            logger.error("Failed to parse SAML response: %s", e)
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# OAuth2 / OIDC Helper
# ═══════════════════════════════════════════════════════════════════════════════

class OIDCHelper:
    """OAuth2 / OpenID Connect flow helper."""

    @staticmethod
    def build_authorization_url(config: SSOProviderConfig, state: str) -> str:
        """Build the OAuth2 authorization redirect URL."""
        params = {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": " ".join(config.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        # Add nonce for OIDC
        if config.protocol == SSOProtocol.OIDC:
            params["nonce"] = secrets.token_urlsafe(16)

        return f"{config.authorization_url}?{urllib.parse.urlencode(params)}"

    @staticmethod
    async def exchange_code(
        config: SSOProviderConfig, code: str
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for tokens."""
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config.token_url,
                    data=payload,
                    headers={"Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "Token exchange failed (%d): %s",
                            resp.status, body[:300],
                        )
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error("Token exchange error: %s", e)
            return None

    @staticmethod
    async def fetch_userinfo(
        config: SSOProviderConfig, access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch user info from the IdP userinfo endpoint."""
        if not config.userinfo_url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.userinfo_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "Userinfo fetch failed (%d): %s",
                            resp.status, body[:300],
                        )
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error("Userinfo fetch error: %s", e)
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# SSO Manager — Main Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class SSOManager:
    """Central SSO manager: provider registry, login initiation, callback handling."""

    def __init__(self):
        self._providers: Dict[str, SSOProviderConfig] = {}
        self._state_manager = SSOStateManager()
        self._saml = SAMLHelper()
        self._oidc = OIDCHelper()

    # ── Provider Management ─────────────────────────────────────────────────

    def register_provider(self, config: SSOProviderConfig) -> None:
        """Register or update an SSO provider configuration."""
        self._providers[config.provider_id] = config
        logger.info(
            "SSO provider registered: %s (%s, %s)",
            config.provider_id, config.display_name, config.protocol.value,
        )

    def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider from the registry."""
        return self._providers.pop(provider_id, None) is not None

    def get_provider(self, provider_id: str) -> Optional[SSOProviderConfig]:
        """Get provider configuration by ID."""
        return self._providers.get(provider_id)

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all registered providers (public info only)."""
        return [p.to_public_dict() for p in self._providers.values()]

    # ── Login Initiation ────────────────────────────────────────────────────

    def initiate_login(self, provider_id: str) -> Optional[Dict[str, str]]:
        """Generate the SSO login redirect URL for a provider.

        Returns {"redirect_url": "...", "state": "..."} or None.
        """
        config = self._providers.get(provider_id)
        if not config or not config.enabled:
            return None

        if config.protocol == SSOProtocol.SAML2:
            state = self._state_manager.generate()
            url = self._saml.build_authn_request_url(config, relay_state=state)
            return {"redirect_url": url, "state": state}

        elif config.protocol in (SSOProtocol.OIDC, SSOProtocol.OAUTH2):
            if not config.client_id:
                logger.warning("SSO provider %s has no client_id configured", provider_id)
                return None
            state = self._state_manager.generate()
            url = self._oidc.build_authorization_url(config, state)
            return {"redirect_url": url, "state": state}

        return None

    # ── Callback Handling ───────────────────────────────────────────────────

    async def handle_callback(
        self,
        provider_id: str,
        code: str = "",
        state: str = "",
        saml_response: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Handle SSO callback from IdP.

        For OIDC/OAuth2: exchanges authorization code for tokens and fetches user info.
        For SAML: parses the SAML response assertion.

        Returns user attributes dict: {email, full_name, provider_user_id, ...}
        or None on failure.
        """
        config = self._providers.get(provider_id)
        if not config or not config.enabled:
            logger.warning("SSO callback for unknown/disabled provider: %s", provider_id)
            return None

        if config.protocol == SSOProtocol.SAML2:
            return await self._handle_saml_callback(config, saml_response, state)
        else:
            return await self._handle_oidc_callback(config, code, state)

    async def _handle_oidc_callback(
        self,
        config: SSOProviderConfig,
        code: str,
        state: str,
    ) -> Optional[Dict[str, Any]]:
        """Handle OAuth2/OIDC callback: code exchange + userinfo."""
        # Validate state (CSRF protection)
        if not self._state_manager.validate(state):
            logger.warning("Invalid or expired SSO state for %s", config.provider_id)
            return None

        if not code:
            logger.warning("No authorization code in SSO callback for %s", config.provider_id)
            return None

        # Exchange code for tokens
        token_data = await self._oidc.exchange_code(config, code)
        if not token_data:
            return None

        access_token = token_data.get("access_token", "")
        id_token_raw = token_data.get("id_token", "")

        # Try to extract user info from ID token first (OIDC)
        user_attrs: Dict[str, Any] = {}
        if id_token_raw:
            user_attrs = self._decode_id_token_claims(id_token_raw)

        # Supplement with userinfo endpoint
        if access_token and config.userinfo_url:
            userinfo = await self._oidc.fetch_userinfo(config, access_token)
            if userinfo:
                user_attrs.update(userinfo)

        if not user_attrs.get("email"):
            logger.warning("SSO callback for %s: no email in user attributes", config.provider_id)
            return None

        # Apply attribute mapping
        mapped = self._map_attributes(user_attrs, config.attribute_map)
        mapped["sso_provider"] = config.provider_id
        mapped["sso_protocol"] = config.protocol.value

        logger.info(
            "SSO authentication successful: provider=%s, email=%s",
            config.provider_id, mapped.get("email"),
        )
        return mapped

    async def _handle_saml_callback(
        self,
        config: SSOProviderConfig,
        saml_response: str,
        relay_state: str,
    ) -> Optional[Dict[str, Any]]:
        """Handle SAML 2.0 callback: parse assertion."""
        if not saml_response:
            logger.warning("No SAMLResponse in callback for %s", config.provider_id)
            return None

        # Validate relay state
        if relay_state and not self._state_manager.validate(relay_state):
            logger.warning("Invalid SAML RelayState for %s", config.provider_id)
            return None

        attributes = self._saml.parse_saml_response(saml_response, config)
        if not attributes:
            return None

        mapped = self._map_attributes(attributes, config.attribute_map)
        mapped["sso_provider"] = config.provider_id
        mapped["sso_protocol"] = config.protocol.value

        logger.info(
            "SAML authentication successful: provider=%s, email=%s",
            config.provider_id, mapped.get("email"),
        )
        return mapped

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _decode_id_token_claims(id_token: str) -> Dict[str, Any]:
        """Decode JWT ID token claims WITHOUT signature verification.

        This is acceptable because we already validated the token exchange
        happened over HTTPS with our client_secret. For extra security,
        production should verify the JWT signature.
        """
        import base64

        try:
            parts = id_token.split(".")
            if len(parts) < 2:
                return {}
            # Decode payload (second part)
            payload = parts[1]
            # Add padding
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as e:
            logger.debug("Failed to decode ID token: %s", e)
            return {}

    @staticmethod
    def _map_attributes(
        raw: Dict[str, Any], mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Map IdP attribute names to local field names."""
        result: Dict[str, Any] = {}
        for idp_key, local_key in mapping.items():
            if idp_key in raw:
                result[local_key] = raw[idp_key]
        # Always include email directly if present
        if "email" in raw and "email" not in result:
            result["email"] = raw["email"]
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════════════════════

sso_manager = SSOManager()


def configure_sso_from_settings() -> None:
    """Read SSO configuration from app settings and register providers.

    Called at startup. Reads from settings or environment variables.
    """
    try:
        from app.config import settings

        # Google Workspace SSO (if configured)
        google_client_id = getattr(settings, "SSO_GOOGLE_CLIENT_ID", "") or ""
        google_client_secret = getattr(settings, "SSO_GOOGLE_CLIENT_SECRET", "") or ""
        if google_client_id:
            base_url = f"http://localhost:{settings.PORT}"
            google_cfg = _google_workspace_config(
                client_id=google_client_id,
                client_secret=google_client_secret,
                redirect_uri=f"{base_url}/api/auth/sso/google/callback",
            )
            sso_manager.register_provider(google_cfg)

        # Azure AD SSO (if configured)
        azure_client_id = getattr(settings, "SSO_AZURE_CLIENT_ID", "") or ""
        azure_client_secret = getattr(settings, "SSO_AZURE_CLIENT_SECRET", "") or ""
        azure_tenant_id = getattr(settings, "SSO_AZURE_TENANT_ID", "common") or "common"
        if azure_client_id:
            base_url = f"http://localhost:{settings.PORT}"
            azure_cfg = _azure_ad_config(
                tenant_id=azure_tenant_id,
                client_id=azure_client_id,
                client_secret=azure_client_secret,
                redirect_uri=f"{base_url}/api/auth/sso/azure_ad/callback",
            )
            sso_manager.register_provider(azure_cfg)

        # SAML 2.0 (generic — if configured)
        saml_idp_sso_url = getattr(settings, "SSO_SAML_IDP_SSO_URL", "") or ""
        if saml_idp_sso_url:
            base_url = f"http://localhost:{settings.PORT}"
            saml_cfg = _saml2_config(
                provider_id="saml_idp",
                display_name=getattr(settings, "SSO_SAML_DISPLAY_NAME", "Corporate SSO"),
                idp_metadata_url=getattr(settings, "SSO_SAML_IDP_METADATA_URL", ""),
                idp_sso_url=saml_idp_sso_url,
                idp_certificate=getattr(settings, "SSO_SAML_IDP_CERTIFICATE", ""),
                sp_entity_id=getattr(settings, "SSO_SAML_SP_ENTITY_ID", f"{base_url}/saml/metadata"),
                sp_acs_url=f"{base_url}/api/auth/sso/saml_idp/callback",
            )
            sso_manager.register_provider(saml_cfg)

        logger.info(
            "SSO configured: %d provider(s) registered",
            len(sso_manager._providers),
        )
    except Exception as e:
        logger.warning("SSO configuration skipped: %s", e)
