from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List, Dict
import json
from pydantic import ValidationError

from src.models.templates import DomainTemplate
from src.services.template_manager import TemplateManager
from src.utils.logger import get_logger
from src.server.middleware.auth import verify_token

router = APIRouter(tags=["templates"])
logger = get_logger()


def get_template_manager():
    return TemplateManager()


@router.get("/templates", response_model=List[DomainTemplate])
async def list_templates(
    manager: TemplateManager = Depends(get_template_manager),
    _token: str = Depends(verify_token),
):
    """List all available domain templates."""
    return manager.get_all_templates()


@router.post("/templates", response_model=Dict[str, str])
async def upload_template(
    file: UploadFile = File(...),
    manager: TemplateManager = Depends(get_template_manager),
    _token: str = Depends(verify_token),
):
    """Upload a new domain template (JSON file)."""
    try:
        content = await file.read()
        data = json.loads(content)

        # Validate against model
        template = DomainTemplate(**data)

        if manager.save_template(template):
            return {"message": f"Template '{template.domain_name}' saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save template")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid template format: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading template: {e}")
        raise HTTPException(status_code=500, detail="Failed to save template")


@router.delete("/templates/{domain_name}", response_model=Dict[str, str])
async def delete_template(
    domain_name: str,
    manager: TemplateManager = Depends(get_template_manager),
    _token: str = Depends(verify_token),
):
    """Delete a domain template by name."""
    if manager.delete_template(domain_name):
        return {"message": f"Template '{domain_name}' deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Template not found")
