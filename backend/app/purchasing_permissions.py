from app.models import Department, User
from app.module_permissions import (
    DepartmentModuleAccess,
    ensure_department_access,
    ensure_department_head,
    resolve_department_access,
)

PurchasingAccess = DepartmentModuleAccess


def resolve_purchasing_access(user: User, department: Department | None) -> PurchasingAccess:
    return resolve_department_access(user, department)


def ensure_purchasing_access(access: PurchasingAccess) -> None:
    ensure_department_access(access, "Purchasing")


def ensure_purchasing_head(access: PurchasingAccess) -> None:
    ensure_department_head(access, "Purchasing")
