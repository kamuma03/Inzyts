"""
API Extraction Agent.

Fetches data from REST API endpoints, handles pagination, and converts
JSON responses to CSV for use in the analysis pipeline.

Follows the same pattern as SQLExtractionAgent.
"""

import uuid
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from src.agents.base import BaseAgent
from src.config import settings
from src.models.state import AnalysisState, Phase
from src.utils.path_validator import ensure_dir
from src.utils.logger import get_logger

logger = get_logger()

# Safety limits — sourced from centralised Settings
_API_MAX_PAGES = settings.api_source.max_pages
_API_REQUEST_TIMEOUT = settings.api_source.request_timeout_seconds
_API_MAX_RESPONSE_MB = settings.api_source.max_response_size_mb

API_AGENT_PROMPT = """You are the APIExtractionAgent for the Inzyts data analysis system.
Your job is to analyze an API response and determine:
1. The JMESPath expression to extract the data array from the response
2. Whether pagination is available and how to request the next page

Given this sample API response (first 2000 chars):
{response_sample}

API URL: {api_url}
User Question: {question}

Return a JSON object with:
{{
  "data_path": "JMESPath expression to extract data array (e.g. 'data.results', 'items', 'records')",
  "pagination": {{
    "type": "none" | "offset" | "cursor" | "next_url",
    "next_param": "parameter name for next page (if applicable)",
    "next_value": "value or path in response for next page token"
  }}
}}

Return ONLY valid JSON. No markdown or explanation.
"""


def _build_auth_headers(api_auth: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Build authentication headers from auth config."""
    if not api_auth:
        return {}

    auth_type = api_auth.get("type", "none")
    headers: Dict[str, str] = {}

    if auth_type == "bearer":
        token = api_auth.get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        key_name = api_auth.get("key_name", "X-API-Key")
        key_value = api_auth.get("key_value", "")
        if key_value:
            headers[key_name] = key_value
    elif auth_type == "basic":
        username = api_auth.get("username", "")
        password = api_auth.get("password", "")
        if username:
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

    return headers


def _is_private_ip(url: str) -> bool:
    """Check if URL resolves to a private/reserved IP range (SSRF protection).

    Returns True (block) when:
    - The hostname is empty or cannot be resolved.
    - The resolved IP is private, loopback, reserved, or link-local.
    - DNS resolution fails (conservative — prevents DNS-rebinding attacks).
    """
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return True

    # Block all loopback / private hostnames — no localhost exemption.
    # Internal services (Redis, Postgres, Jupyter) listen on these addresses.
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True

    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except (socket.gaierror, ValueError):
        # DNS resolution failed — block conservatively to prevent
        # DNS-rebinding attacks where the first lookup fails but a
        # subsequent one resolves to an internal IP.
        return True


def _extract_data_with_jmespath(data: Any, path: Optional[str]) -> List[Dict]:
    """Extract a data array from a JSON response using JMESPath."""
    if not path:
        # If no path given, try common patterns
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Try common keys
            for key in ("data", "results", "items", "records", "rows", "entries"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # If dict has nested data key
            if "data" in data and isinstance(data["data"], dict):
                for key in ("results", "items", "records"):
                    if key in data["data"] and isinstance(data["data"][key], list):
                        return data["data"][key]
            # Single-item response: wrap in list
            return [data]
        return [data]

    try:
        import jmespath
        result = jmespath.search(path, data)
        if isinstance(result, list):
            return result
        if result is not None:
            return [result]
        return []
    except ImportError:
        # Fallback: simple dot-path navigation
        current = data
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return [data] if isinstance(data, list) else []
        return current if isinstance(current, list) else [current]


class APIExtractionAgent(BaseAgent):
    """Agent that fetches data from REST APIs and converts to CSV."""

    def __init__(self):
        super().__init__(
            name="APIExtractionAgent",
            phase=Phase.PHASE_1,
            system_prompt=API_AGENT_PROMPT,
        )

    def process(self, state: AnalysisState, **kwargs) -> Dict[str, Any]:
        logger.info("APIExtractionAgent starting...")

        intent = state.user_intent
        api_url = getattr(intent, "api_url", None)
        api_headers = getattr(intent, "api_headers", None) or {}
        api_auth = getattr(intent, "api_auth", None)
        json_path = getattr(intent, "json_path", None)
        question = intent.analysis_question

        if not api_url:
            logger.error("APIExtractionAgent requires api_url in UserIntent.")
            return {"errors": ["No api_url provided for APIExtractionAgent."]}

        # SSRF protection: block private IPs. Intentionally re-checked here
        # (also checked in /api-preview route) to guard against DNS rebinding
        # between preview and actual extraction.
        if _is_private_ip(api_url):
            logger.warning(f"APIExtractionAgent blocked private IP: {api_url}")
            return {"errors": ["API URL resolves to a private/reserved IP address."]}

        # Build request headers
        headers = {**api_headers}
        headers.update(_build_auth_headers(api_auth))
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", "Inzyts-APIExtractionAgent/1.0")

        try:
            all_records: List[Dict] = []
            current_url = api_url
            total_size = 0

            for page in range(_API_MAX_PAGES):
                logger.info(f"Fetching page {page + 1}: {current_url[:100]}...")

                response = requests.get(
                    current_url,
                    headers=headers,
                    timeout=_API_REQUEST_TIMEOUT,
                )
                response.raise_for_status()

                # Check response size
                content_size = len(response.content)
                total_size += content_size
                if total_size > _API_MAX_RESPONSE_MB * 1024 * 1024:
                    logger.warning(
                        f"Total response size ({total_size / 1024 / 1024:.1f} MB) "
                        f"exceeds limit of {_API_MAX_RESPONSE_MB} MB. Stopping pagination."
                    )
                    break

                data = response.json()
                records = _extract_data_with_jmespath(data, json_path)
                if not records:
                    break

                all_records.extend(records)
                logger.info(f"Page {page + 1}: extracted {len(records)} records (total: {len(all_records)})")

                # Simple pagination detection
                next_url = None
                if isinstance(data, dict):
                    # Check for next URL in common locations
                    next_url = (
                        data.get("next")
                        or data.get("next_url")
                        or data.get("paging", {}).get("next")
                        or data.get("pagination", {}).get("next_url")
                    )
                    # Check Link header
                    if not next_url:
                        link_header = response.headers.get("Link", "")
                        if 'rel="next"' in link_header:
                            for part in link_header.split(","):
                                if 'rel="next"' in part:
                                    next_url = part.split(";")[0].strip().strip("<>")
                                    break

                if not next_url:
                    break
                current_url = next_url

            if not all_records:
                return {"errors": ["API returned no data records."]}

            # Convert to DataFrame and save as CSV
            df = pd.json_normalize(all_records)

            output_dir = Path(settings.upload_dir).resolve()
            ensure_dir(output_dir)

            filename = f"api_extract_{uuid.uuid4().hex[:8]}.csv"
            output_path = str(output_dir / filename)
            df.to_csv(output_path, index=False)

            logger.info(
                f"APIExtractionAgent saved {len(df)} rows, {len(df.columns)} columns to {output_path}"
            )
            return {"csv_path": output_path}

        except requests.exceptions.Timeout:
            return {"errors": [f"API request timed out after {_API_REQUEST_TIMEOUT}s."]}
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            return {"errors": [f"API returned HTTP {status}."]}
        except Exception as e:
            logger.error(f"APIExtractionAgent failed: {e}")
            return {"errors": [f"APIExtractionAgent failed: {type(e).__name__}: {e}"]}
