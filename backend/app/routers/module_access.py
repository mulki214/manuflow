from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Department, User
from app.module_permissions import resolve_department_access, resolve_department_membership
from app.purchasing_permissions import resolve_purchasing_access
from app.schemas import ModuleAccessResponse

router = APIRouter(prefix="/module-access", tags=["Module Access"])


@router.get("/purchasing", response_model=ModuleAccessResponse)
async def purchasing_module_access(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ModuleAccessResponse:
    department = await db.get(Department, settings.purchasing_department_code)
    access = resolve_purchasing_access(current_user, department)
    return ModuleAccessResponse(
        department_code=settings.purchasing_department_code,
        can_access=access.can_access,
        is_pic=access.is_pic,
        is_head=access.is_head,
        can_review=access.can_review,
    )


@router.get("/sales-order", response_model=ModuleAccessResponse)
async def sales_order_module_access(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ModuleAccessResponse:
    department = await db.get(Department, settings.sales_department_code)
    access = resolve_department_access(current_user, department)
    return ModuleAccessResponse(
        module="sales_order",
        department_code=settings.sales_department_code,
        can_access=access.can_access,
        is_pic=access.is_pic,
        is_head=access.is_head,
        can_review=access.can_review,
    )


@router.get("/receiving", response_model=ModuleAccessResponse)
async def receiving_module_access(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ModuleAccessResponse:
    department = await db.get(Department, settings.warehouse_department_code)
    access = resolve_department_membership(current_user, department)
    return ModuleAccessResponse(
        module="receiving",
        department_code=settings.warehouse_department_code,
        can_access=access.can_access,
        is_pic=access.is_pic,
        is_head=access.is_head,
        can_review=access.is_pic or access.is_head,
    )


@router.get("/warehouse", response_model=ModuleAccessResponse)
async def warehouse_module_access(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ModuleAccessResponse:
    department = await db.get(Department, settings.warehouse_department_code)
    access = resolve_department_membership(current_user, department)
    return ModuleAccessResponse(
        module="warehouse",
        department_code=settings.warehouse_department_code,
        can_access=access.can_access,
        is_pic=access.is_pic,
        is_head=access.is_head,
        can_review=access.is_pic or access.is_head,
    )


@router.get("/production", response_model=ModuleAccessResponse)
async def production_module_access(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ModuleAccessResponse:
    department = await db.get(Department, settings.production_department_code)
    access = resolve_department_membership(current_user, department)
    return ModuleAccessResponse(
        module="production",
        department_code=settings.production_department_code,
        can_access=access.can_access,
        is_pic=access.is_pic,
        is_head=access.is_head,
        can_review=access.is_pic or access.is_head,
    )


@router.get("/quality", response_model=ModuleAccessResponse)
async def quality_module_access(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ModuleAccessResponse:
    department = await db.get(Department, settings.quality_department_code)
    access = resolve_department_membership(current_user, department)
    return ModuleAccessResponse(
        module="quality",
        department_code=settings.quality_department_code,
        can_access=access.can_access,
        is_pic=access.is_pic,
        is_head=access.is_head,
        can_review=access.is_pic or access.is_head,
    )
