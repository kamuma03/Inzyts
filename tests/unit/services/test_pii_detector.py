"""Tests for PII Detection & Masking Service."""

import json
import pytest
import nbformat
from pathlib import Path

from src.services.pii_detector import PIIDetector, PIIFinding, PIIScanResult


class TestPIIDetectorScanText:
    """Tests for PIIDetector.scan_text()."""

    def test_detect_email(self):
        findings = PIIDetector.scan_text("Contact john@example.com for info", "test")
        assert len(findings) == 1
        assert findings[0].pii_type == "email"
        assert findings[0].severity == "medium"
        assert "j***" in findings[0].value  # partially masked

    def test_detect_multiple_emails(self):
        text = "alice@foo.com and bob@bar.org"
        findings = PIIDetector.scan_text(text, "cell 1")
        emails = [f for f in findings if f.pii_type == "email"]
        assert len(emails) == 2

    def test_detect_phone(self):
        findings = PIIDetector.scan_text("Call 555-123-4567 today", "cell 2")
        phones = [f for f in findings if f.pii_type == "phone"]
        assert len(phones) == 1
        assert phones[0].severity == "medium"
        assert "4567" in phones[0].value  # last 4 visible

    def test_detect_phone_with_country_code(self):
        findings = PIIDetector.scan_text("Phone: +1 (555) 123-4567", "test")
        phones = [f for f in findings if f.pii_type == "phone"]
        assert len(phones) >= 1

    def test_detect_ssn(self):
        findings = PIIDetector.scan_text("SSN is 123-45-6789", "cell 3")
        ssns = [f for f in findings if f.pii_type == "ssn"]
        assert len(ssns) == 1
        assert ssns[0].severity == "high"
        assert "6789" in ssns[0].value  # last 4 visible
        assert "123" not in ssns[0].value  # first 3 masked

    def test_detect_credit_card(self):
        findings = PIIDetector.scan_text("Card: 4111-1111-1111-1111", "test")
        cards = [f for f in findings if f.pii_type == "credit_card"]
        assert len(cards) == 1
        assert cards[0].severity == "high"
        assert "1111" in cards[0].value  # last 4 visible

    def test_detect_ip_address(self):
        findings = PIIDetector.scan_text("Server at 192.168.1.100", "test")
        ips = [f for f in findings if f.pii_type == "ip_address"]
        assert len(ips) == 1
        assert ips[0].severity == "low"

    def test_ignore_common_ips(self):
        findings = PIIDetector.scan_text("localhost 127.0.0.1 and 0.0.0.0", "test")
        ips = [f for f in findings if f.pii_type == "ip_address"]
        assert len(ips) == 0

    def test_no_pii_in_clean_text(self):
        findings = PIIDetector.scan_text("The average sales in Q3 were $1.2M", "test")
        assert len(findings) == 0

    def test_empty_text(self):
        findings = PIIDetector.scan_text("", "test")
        assert len(findings) == 0

    def test_multiple_pii_types(self):
        text = "Email: test@x.com, SSN: 111-22-3333, Phone: 555-000-1234"
        findings = PIIDetector.scan_text(text, "multi")
        types = {f.pii_type for f in findings}
        assert "email" in types
        assert "ssn" in types
        assert "phone" in types

    def test_location_preserved(self):
        findings = PIIDetector.scan_text("foo@bar.com", "cell 5 (markdown)")
        assert findings[0].location == "cell 5 (markdown)"


class TestPIIDetectorScanNotebook:
    """Tests for PIIDetector.scan_notebook()."""

    def test_scan_notebook_with_pii(self, tmp_path):
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_markdown_cell("Contact: alice@example.com"))
        nb.cells.append(nbformat.v4.new_code_cell("# SSN: 123-45-6789"))
        path = tmp_path / "test.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        result = PIIDetector.scan_notebook(str(path))
        assert isinstance(result, PIIScanResult)
        assert result.has_pii is True
        assert result.scanned_cells == 2
        assert len(result.findings) >= 2
        assert result.scan_duration_ms >= 0

    def test_scan_notebook_clean(self, tmp_path):
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_markdown_cell("Average sales: $100K"))
        nb.cells.append(nbformat.v4.new_code_cell("import pandas as pd"))
        path = tmp_path / "clean.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        result = PIIDetector.scan_notebook(str(path))
        assert result.has_pii is False
        assert len(result.findings) == 0
        assert result.scanned_cells == 2

    def test_scan_notebook_missing_file(self):
        result = PIIDetector.scan_notebook("/nonexistent/path.ipynb")
        assert result.has_pii is False
        assert result.scanned_cells == 0

    def test_scan_notebook_deduplicates(self, tmp_path):
        nb = nbformat.v4.new_notebook()
        # Same email in multiple cells
        nb.cells.append(nbformat.v4.new_markdown_cell("alice@example.com"))
        nb.cells.append(nbformat.v4.new_markdown_cell("alice@example.com again"))
        path = tmp_path / "dup.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        result = PIIDetector.scan_notebook(str(path))
        emails = [f for f in result.findings if f.pii_type == "email"]
        assert len(emails) == 1  # deduplicated

    def test_scan_notebook_code_outputs(self, tmp_path):
        nb = nbformat.v4.new_notebook()
        code_cell = nbformat.v4.new_code_cell("print('data')")
        code_cell.outputs = [
            nbformat.v4.new_output(
                output_type="stream",
                text="User SSN: 999-88-7777\n",
            )
        ]
        nb.cells.append(code_cell)
        path = tmp_path / "output.ipynb"
        with open(path, "w") as f:
            nbformat.write(nb, f)

        result = PIIDetector.scan_notebook(str(path))
        assert result.has_pii is True
        ssns = [f for f in result.findings if f.pii_type == "ssn"]
        assert len(ssns) == 1


class TestPIIDetectorMasking:
    """Tests for PIIDetector.mask_text() and mask_notebook_content()."""

    def test_mask_email(self):
        masked = PIIDetector.mask_text("Email: john@example.com")
        assert "[EMAIL]" in masked
        assert "john@example.com" not in masked

    def test_mask_ssn(self):
        masked = PIIDetector.mask_text("SSN: 123-45-6789")
        assert "[SSN]" in masked
        assert "123-45-6789" not in masked

    def test_mask_phone(self):
        masked = PIIDetector.mask_text("Phone: 555-123-4567")
        assert "[PHONE]" in masked

    def test_mask_credit_card(self):
        masked = PIIDetector.mask_text("Card: 4111-1111-1111-1111")
        assert "[CREDIT_CARD]" in masked

    def test_mask_ip_preserves_common(self):
        masked = PIIDetector.mask_text("localhost is 127.0.0.1")
        assert "127.0.0.1" in masked  # common IP preserved

    def test_mask_ip_masks_private(self):
        masked = PIIDetector.mask_text("server at 10.0.5.100")
        assert "[IP_ADDRESS]" in masked

    def test_mask_clean_text_unchanged(self):
        text = "Sales were $1.2M in Q3 2025"
        assert PIIDetector.mask_text(text) == text

    def test_mask_notebook_content(self):
        cells = [
            "Contact: alice@test.com",
            "No PII here",
            "SSN: 111-22-3333",
        ]
        masked = PIIDetector.mask_notebook_content(cells)
        assert len(masked) == 3
        assert "[EMAIL]" in masked[0]
        assert masked[1] == "No PII here"
        assert "[SSN]" in masked[2]

    def test_mask_multiple_pii_in_same_text(self):
        text = "Email: a@b.com, SSN: 111-22-3333"
        masked = PIIDetector.mask_text(text)
        assert "[EMAIL]" in masked
        assert "[SSN]" in masked


class TestPIIFindingModel:
    """Tests for PIIFinding and PIIScanResult Pydantic models."""

    def test_pii_finding_creation(self):
        f = PIIFinding(
            pii_type="email",
            value="j***@example.com",
            location="cell 1",
            severity="medium",
        )
        assert f.pii_type == "email"
        assert f.severity == "medium"

    def test_pii_scan_result_creation(self):
        result = PIIScanResult(
            has_pii=True,
            findings=[
                PIIFinding(pii_type="ssn", value="***", location="cell 1", severity="high")
            ],
            scanned_cells=5,
            scan_duration_ms=12.5,
        )
        assert result.has_pii is True
        assert len(result.findings) == 1
        assert result.scanned_cells == 5

    def test_pii_scan_result_serialization(self):
        result = PIIScanResult(has_pii=False, findings=[], scanned_cells=0, scan_duration_ms=0.0)
        data = result.model_dump()
        assert data["has_pii"] is False
        assert data["findings"] == []
