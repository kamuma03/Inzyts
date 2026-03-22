"""
PII Detection & Masking Service.

Scans notebook text content for personally identifiable information (PII)
using regex-based pattern matching. Returns findings with type, location,
and severity. Optionally masks detected PII with redacted placeholders.
"""

import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

import nbformat
from pydantic import BaseModel

from src.utils.logger import get_logger

logger = get_logger()


class PIIFinding(BaseModel):
    """A single PII detection result."""

    pii_type: str  # "email", "phone", "ssn", "credit_card", "ip_address"
    value: str  # The matched text (truncated/masked in output)
    location: str  # "cell 3, line 5" or "code output, cell 2"
    severity: str  # "high", "medium", "low"


class PIIScanResult(BaseModel):
    """Result of a PII scan across a notebook."""

    has_pii: bool
    findings: List[PIIFinding]
    scanned_cells: int
    scan_duration_ms: float


# Pattern name -> (compiled regex, severity, replacement placeholder)
_PII_PATTERNS: Dict[str, Tuple[re.Pattern, str, str]] = {
    "email": (
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
        "medium",
        "[EMAIL]",
    ),
    "phone": (
        re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        "medium",
        "[PHONE]",
    ),
    "ssn": (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "high",
        "[SSN]",
    ),
    "credit_card": (
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "high",
        "[CREDIT_CARD]",
    ),
    "ip_address": (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        "low",
        "[IP_ADDRESS]",
    ),
}

# Common false-positive IPs to ignore (localhost, broadcast, etc.)
_IGNORE_IPS = {"0.0.0.0", "127.0.0.1", "255.255.255.255", "192.168.0.1", "10.0.0.1"}


class PIIDetector:
    """Regex-based PII detection and masking for notebook content."""

    @staticmethod
    def scan_text(text: str, location: str = "") -> List[PIIFinding]:
        """Scan a single text block for PII patterns.

        Args:
            text: The text content to scan.
            location: Human-readable location descriptor.

        Returns:
            List of PIIFinding objects for each match.
        """
        findings: List[PIIFinding] = []
        for pii_type, (pattern, severity, _) in _PII_PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group()

                # Filter false positives
                if pii_type == "ip_address" and value in _IGNORE_IPS:
                    continue

                # Partially mask the value for safe display
                masked_value = PIIDetector._partial_mask(value, pii_type)

                findings.append(
                    PIIFinding(
                        pii_type=pii_type,
                        value=masked_value,
                        location=location,
                        severity=severity,
                    )
                )
        return findings

    @staticmethod
    def scan_notebook(notebook_path: str) -> PIIScanResult:
        """Read an .ipynb file and scan all cells for PII.

        Scans markdown cell content, code cell source, and code cell
        text outputs (stream, execute_result, display_data).

        Args:
            notebook_path: Path to the .ipynb file.

        Returns:
            PIIScanResult with all findings.
        """
        start = time.monotonic()
        findings: List[PIIFinding] = []
        scanned_cells = 0

        path = Path(notebook_path)
        if not path.exists():
            logger.warning(f"PII scan: notebook not found at {notebook_path}")
            return PIIScanResult(
                has_pii=False, findings=[], scanned_cells=0, scan_duration_ms=0.0
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                nb = nbformat.read(f, as_version=4)
        except Exception as e:
            logger.error(f"PII scan: failed to read notebook: {e}")
            return PIIScanResult(
                has_pii=False, findings=[], scanned_cells=0, scan_duration_ms=0.0
            )

        for idx, cell in enumerate(nb.cells):
            scanned_cells += 1
            cell_loc = f"cell {idx + 1}"

            # Scan cell source
            cell_findings = PIIDetector.scan_text(
                cell.source, f"{cell_loc} ({cell.cell_type})"
            )
            findings.extend(cell_findings)

            # Scan code cell outputs
            if cell.cell_type == "code" and hasattr(cell, "outputs"):
                for out_idx, output in enumerate(cell.outputs):
                    out_text = ""
                    if output.get("output_type") == "stream":
                        out_text = output.get("text", "")
                    elif output.get("output_type") in (
                        "execute_result",
                        "display_data",
                    ):
                        data = output.get("data", {})
                        out_text = data.get("text/plain", "")
                    elif output.get("output_type") == "error":
                        out_text = "\n".join(output.get("traceback", []))

                    if out_text:
                        out_findings = PIIDetector.scan_text(
                            out_text, f"{cell_loc}, output {out_idx + 1}"
                        )
                        findings.extend(out_findings)

        elapsed_ms = (time.monotonic() - start) * 1000

        # Deduplicate by (pii_type, value) keeping first occurrence
        seen = set()
        unique_findings = []
        for f in findings:
            key = (f.pii_type, f.value)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        return PIIScanResult(
            has_pii=len(unique_findings) > 0,
            findings=unique_findings,
            scanned_cells=scanned_cells,
            scan_duration_ms=round(elapsed_ms, 2),
        )

    @staticmethod
    def mask_text(text: str) -> str:
        """Replace detected PII in text with redacted placeholders.

        Args:
            text: The text to mask.

        Returns:
            Text with PII replaced by placeholders like [EMAIL], [SSN], etc.
        """
        masked = text
        for pii_type, (pattern, _, placeholder) in _PII_PATTERNS.items():
            if pii_type == "ip_address":
                # Only mask non-common IPs
                def _ip_replacer(m: re.Match) -> str:
                    return m.group() if m.group() in _IGNORE_IPS else "[IP_ADDRESS]"

                masked = pattern.sub(_ip_replacer, masked)
            else:
                masked = pattern.sub(placeholder, masked)
        return masked

    @staticmethod
    def mask_notebook_content(cells_text: List[str]) -> List[str]:
        """Apply PII masking to a list of cell text contents.

        Args:
            cells_text: List of cell source strings.

        Returns:
            List of masked cell source strings.
        """
        return [PIIDetector.mask_text(text) for text in cells_text]

    @staticmethod
    def _partial_mask(value: str, pii_type: str) -> str:
        """Partially mask a PII value for safe display in findings.

        Shows enough to identify the match without fully exposing the data.
        """
        if pii_type == "email":
            parts = value.split("@")
            if len(parts) == 2:
                local = parts[0]
                masked_local = local[0] + "***" if len(local) > 1 else "***"
                return f"{masked_local}@{parts[1]}"
        elif pii_type == "ssn":
            return f"***-**-{value[-4:]}"
        elif pii_type == "credit_card":
            clean = value.replace("-", "").replace(" ", "")
            return f"****-****-****-{clean[-4:]}"
        elif pii_type == "phone":
            clean = re.sub(r"[^\d]", "", value)
            if len(clean) >= 4:
                return f"***-***-{clean[-4:]}"
        # Default: show first 3 chars + mask
        if len(value) > 3:
            return value[:3] + "***"
        return "***"
