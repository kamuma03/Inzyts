import json
import os
from pathlib import Path
from typing import List, Optional

from ..models.templates import DomainTemplate
from ..utils.logger import get_logger

logger = get_logger()


class TemplateManager:
    """Manages loading and matching of Domain Templates."""

    def __init__(self, template_dir: Optional[str] = None):
        self.templates: List[DomainTemplate] = []

        # Default to src/config/templates
        if not template_dir:
            base_dir = Path(__file__).resolve().parent.parent
            template_dir = str(base_dir / "config" / "templates")

        self.template_dir = template_dir
        self._load_templates()

    def _load_templates(self):
        """Load templates from JSON files."""
        template_path = Path(self.template_dir)
        if not template_path.exists():
            logger.warning(f"Template directory not found: {self.template_dir}")
            return

        for filename in os.listdir(self.template_dir):
            if filename.endswith(".json"):
                try:
                    path = str(template_path / filename)
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        template = DomainTemplate(**data)
                        self.templates.append(template)
                except Exception as e:
                    logger.error(f"Failed to load template {filename}: {e}")

        logger.info(f"Loaded {len(self.templates)} domain templates")

    def detect_domain(self, columns: List[str]) -> Optional[DomainTemplate]:
        """
        Detect the most likely domain for the given columns.
        Returns the template with the highest match score if > threshold.
        """
        best_score = 0.0
        best_template = None

        for template in self.templates:
            score = template.match_score(columns)
            if score > best_score:
                best_score = score
                best_template = template

        # threshold
        if (
            best_score >= 0.3 and best_template is not None
        ):  # Match at least 30% of concepts
            logger.info(
                f"Detected domain: {best_template.domain_name} (score: {best_score:.2f})"
            )
            return best_template

        return None

    def save_template(self, template: DomainTemplate) -> bool:
        """Save a new template or update an existing one."""
        try:
            filename = f"{template.domain_name.lower().replace(' ', '_')}.json"
            path = str(Path(self.template_dir) / filename)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(template.model_dump(), f, indent=4)

            # Update memory
            existing_idx = next(
                (
                    i
                    for i, t in enumerate(self.templates)
                    if t.domain_name == template.domain_name
                ),
                -1,
            )
            if existing_idx >= 0:
                self.templates[existing_idx] = template
            else:
                self.templates.append(template)

            logger.info(f"Saved template: {template.domain_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            return False

    def delete_template(self, domain_name: str) -> bool:
        """Delete a template by domain name."""
        try:
            # Find in memory
            template = next(
                (t for t in self.templates if t.domain_name == domain_name), None
            )
            if not template:
                return False

            # Delete file
            filename = f"{template.domain_name.lower().replace(' ', '_')}.json"
            file_path = Path(self.template_dir) / filename

            if file_path.exists():
                os.remove(file_path)

            # Remove from memory
            self.templates = [t for t in self.templates if t.domain_name != domain_name]

            logger.info(f"Deleted template: {domain_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            return False

    def get_all_templates(self) -> List[DomainTemplate]:
        """Return all loaded templates."""
        return self.templates
