"""Real EMS (Equipment Management System) adapter.

Supports uploading test results to production EMS systems.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class EMSAuthType(str, Enum):
    """Authentication types for EMS."""
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"


@dataclass
class EMSConfig:
    """Configuration for EMS connection.

    Attributes:
        endpoint: EMS API endpoint URL
        auth_type: Authentication method
        api_key: API key for authentication
        bearer_token: OAuth/JWT bearer token
        username: Username for basic auth
        password: Password for basic auth
        timeout_seconds: Request timeout
        max_retries: Maximum retry attempts
        retry_delay_seconds: Delay between retries
    """
    endpoint: str
    auth_type: EMSAuthType = EMSAuthType.API_KEY
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5


class EMSAdapter(ABC):
    """Abstract base class for EMS adapters."""

    @abstractmethod
    def upload_result(self, result: Dict[str, Any]) -> bool:
        """Upload test result to EMS.

        Args:
            result: Test result dictionary

        Returns:
            True if upload successful, False otherwise
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check EMS connectivity.

        Returns:
            True if EMS is reachable, False otherwise
        """
        pass


class HTTPBasedEMSAdapter(EMSAdapter):
    """HTTP/REST based EMS adapter.

    Supports:
    - REST API with JSON payloads
    - Multiple authentication methods
    - Automatic retry with exponential backoff
    - Connection pooling
    """

    def __init__(self, config: EMSConfig):
        self.config = config
        self._session = None
        self._last_error: Optional[str] = None

    def _get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            try:
                import requests
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry

                self._session = requests.Session()

                # Configure retries for connection errors
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                )

                adapter = HTTPAdapter(
                    max_retries=retry_strategy,
                    pool_connections=10,
                    pool_maxsize=10
                )

                self._session.mount("http://", adapter)
                self._session.mount("https://", adapter)

            except ImportError:
                raise RuntimeError("requests library is required for HTTP EMS adapter")

        return self._session

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ServerTestSystem/1.0"
        }

        if self.config.auth_type == EMSAuthType.API_KEY and self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        elif self.config.auth_type == EMSAuthType.BEARER_TOKEN and self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"

        return headers

    def _get_auth(self) -> Optional[tuple]:
        """Get basic auth tuple if configured."""
        if (self.config.auth_type == EMSAuthType.BASIC_AUTH and
            self.config.username and self.config.password):
            return (self.config.username, self.config.password)
        return None

    def health_check(self) -> bool:
        """Check EMS connectivity."""
        try:
            import requests

            session = self._get_session()
            response = session.get(
                f"{self.config.endpoint}/health",
                headers=self._get_headers(),
                auth=self._get_auth(),
                timeout=self.config.timeout_seconds
            )

            return response.status_code == 200

        except Exception as e:
            self._last_error = str(e)
            return False

    def upload_result(self, result: Dict[str, Any]) -> bool:
        """Upload test result to EMS with retry logic."""
        import requests

        url = f"{self.config.endpoint}/api/v1/test-results"

        # Prepare payload
        payload = self._prepare_payload(result)

        for attempt in range(self.config.max_retries):
            try:
                session = self._get_session()
                response = session.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    auth=self._get_auth(),
                    timeout=self.config.timeout_seconds
                )

                if response.status_code in [200, 201]:
                    return True
                elif response.status_code == 401:
                    self._last_error = "Authentication failed"
                    return False  # Don't retry auth failures
                elif response.status_code == 429:
                    self._last_error = "Rate limited"
                    # Retry after delay
                    time.sleep(self.config.retry_delay_seconds * (attempt + 1))
                else:
                    self._last_error = f"HTTP {response.status_code}: {response.text}"
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay_seconds)

            except requests.exceptions.Timeout:
                self._last_error = "Request timeout"
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_seconds)

            except requests.exceptions.ConnectionError as e:
                self._last_error = f"Connection error: {str(e)}"
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_seconds * (attempt + 1))

            except Exception as e:
                self._last_error = f"Unexpected error: {str(e)}"
                return False

        return False

    def _prepare_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare result payload for EMS.

        Adds metadata and formats the result for EMS consumption.
        """
        return {
            "uploaded_at": datetime.now().isoformat(),
            "test_system_version": "1.0.0",
            "result": result
        }

    def get_last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error


class WebhookEMSAdapter(EMSAdapter):
    """Webhook-based EMS adapter for simple HTTP callbacks.

    Useful for integration with CI/CD systems or simple endpoints.
    """

    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret
        self._last_error: Optional[str] = None

    def health_check(self) -> bool:
        """Simple webhook health check (HEAD request)."""
        try:
            import requests

            response = requests.head(
                self.webhook_url,
                timeout=10
            )
            return response.status_code < 500

        except Exception as e:
            self._last_error = str(e)
            return False

    def upload_result(self, result: Dict[str, Any]) -> bool:
        """Send result to webhook endpoint."""
        import requests
        import hmac
        import hashlib

        payload = {
            "timestamp": datetime.now().isoformat(),
            "result": result
        }

        headers = {
            "Content-Type": "application/json"
        }

        # Add signature if secret is configured
        if self.secret:
            payload_bytes = json.dumps(payload).encode()
            signature = hmac.new(
                self.secret.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201, 204]:
                return True
            else:
                self._last_error = f"HTTP {response.status_code}"
                return False

        except Exception as e:
            self._last_error = str(e)
            return False

    def get_last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error


class EMSAdapterFactory:
    """Factory for creating EMS adapters."""

    @staticmethod
    def create_adapter(config: Dict[str, Any]) -> EMSAdapter:
        """Create appropriate EMS adapter from configuration.

        Args:
            config: Configuration dictionary with 'type' and adapter-specific settings

        Returns:
            Configured EMSAdapter instance
        """
        adapter_type = config.get("type", "http")

        if adapter_type == "http":
            ems_config = EMSConfig(
                endpoint=config["endpoint"],
                auth_type=EMSAuthType(config.get("auth_type", "api_key")),
                api_key=config.get("api_key"),
                bearer_token=config.get("bearer_token"),
                username=config.get("username"),
                password=config.get("password"),
                timeout_seconds=config.get("timeout_seconds", 30),
                max_retries=config.get("max_retries", 3),
                retry_delay_seconds=config.get("retry_delay_seconds", 5)
            )
            return HTTPBasedEMSAdapter(ems_config)

        elif adapter_type == "webhook":
            return WebhookEMSAdapter(
                webhook_url=config["webhook_url"],
                secret=config.get("secret")
            )

        else:
            raise ValueError(f"Unknown EMS adapter type: {adapter_type}")
