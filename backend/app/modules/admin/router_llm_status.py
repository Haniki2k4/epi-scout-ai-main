from fastapi import APIRouter, Depends

from ..auth.security import require_admin_role
from ..news import crawler


router = APIRouter(prefix="/api/admin", tags=["admin-llm-status"])


@router.get("/llm-status")
def get_llm_status(_=Depends(require_admin_role)):
    return crawler.get_llm_runtime_status()
