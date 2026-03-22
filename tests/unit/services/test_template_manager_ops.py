"""
Tests for TemplateManager — save, delete, get_all, and detect_domain operations.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock

from src.services.template_manager import TemplateManager
from src.models.templates import DomainTemplate, DomainConcept


def _make_template(name="Healthcare", synonyms=None):
    return DomainTemplate(
        domain_name=name,
        description=f"{name} domain template",
        concepts=[
            DomainConcept(
                name="Patient ID",
                description="Unique patient identifier",
                synonyms=synonyms or ["patient_id", "patientid"],
            ),
            DomainConcept(
                name="Diagnosis",
                description="Medical diagnosis code",
                synonyms=["diagnosis", "icd_code"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# TemplateManager initialization
# ---------------------------------------------------------------------------

class TestInit:

    def test_loads_from_directory(self, tmp_path):
        template = _make_template()
        f = tmp_path / "healthcare.json"
        f.write_text(json.dumps(template.model_dump()))

        mgr = TemplateManager(template_dir=str(tmp_path))
        assert len(mgr.templates) == 1
        assert mgr.templates[0].domain_name == "Healthcare"

    def test_empty_directory(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        assert len(mgr.templates) == 0

    def test_missing_directory(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path / "nonexistent"))
        assert len(mgr.templates) == 0

    def test_invalid_json_skipped(self, tmp_path):
        (tmp_path / "bad.json").write_text("NOT JSON")
        mgr = TemplateManager(template_dir=str(tmp_path))
        assert len(mgr.templates) == 0


# ---------------------------------------------------------------------------
# save_template
# ---------------------------------------------------------------------------

class TestSaveTemplate:

    def test_save_new_template(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        template = _make_template()

        result = mgr.save_template(template)

        assert result is True
        assert len(mgr.templates) == 1

        # Verify file on disk
        path = tmp_path / "healthcare.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["domain_name"] == "Healthcare"

    def test_update_existing_template(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        template_v1 = _make_template(name="Finance")
        mgr.save_template(template_v1)
        assert len(mgr.templates) == 1

        template_v2 = _make_template(name="Finance")
        template_v2.description = "Updated finance domain"
        mgr.save_template(template_v2)

        assert len(mgr.templates) == 1  # Replaced, not appended
        assert mgr.templates[0].description == "Updated finance domain"

    def test_save_failure_returns_false(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        template = _make_template()

        with patch("builtins.open", side_effect=PermissionError("denied")):
            result = mgr.save_template(template)
            assert result is False


# ---------------------------------------------------------------------------
# delete_template
# ---------------------------------------------------------------------------

class TestDeleteTemplate:

    def test_delete_existing(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        template = _make_template()
        mgr.save_template(template)
        assert len(mgr.templates) == 1

        result = mgr.delete_template("Healthcare")

        assert result is True
        assert len(mgr.templates) == 0
        assert not (tmp_path / "healthcare.json").exists()

    def test_delete_nonexistent(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        result = mgr.delete_template("Ghost")
        assert result is False

    def test_delete_failure_returns_false(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        template = _make_template()
        mgr.save_template(template)

        with patch("os.remove", side_effect=OSError("disk error")):
            result = mgr.delete_template("Healthcare")
            assert result is False


# ---------------------------------------------------------------------------
# get_all_templates
# ---------------------------------------------------------------------------

class TestGetAll:

    def test_returns_all(self, tmp_path):
        mgr = TemplateManager(template_dir=str(tmp_path))
        mgr.save_template(_make_template("A"))
        mgr.save_template(_make_template("B"))

        all_templates = mgr.get_all_templates()
        assert len(all_templates) == 2


# ---------------------------------------------------------------------------
# detect_domain
# ---------------------------------------------------------------------------

class TestDetectDomain:

    def test_match_above_threshold(self, tmp_path):
        template = _make_template(synonyms=["patient_id", "patientid"])
        f = tmp_path / "healthcare.json"
        f.write_text(json.dumps(template.model_dump()))

        mgr = TemplateManager(template_dir=str(tmp_path))

        # Both synonyms match -> score = 2/2 = 1.0 > 0.3 threshold
        result = mgr.detect_domain(["patient_id", "diagnosis"])
        assert result is not None
        assert result.domain_name == "Healthcare"

    def test_no_match_below_threshold(self, tmp_path):
        template = _make_template()
        f = tmp_path / "healthcare.json"
        f.write_text(json.dumps(template.model_dump()))

        mgr = TemplateManager(template_dir=str(tmp_path))

        result = mgr.detect_domain(["totally_unrelated", "another_column"])
        assert result is None
