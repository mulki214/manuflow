from dataclasses import dataclass

from fastapi import HTTPException, status

from app.models import AccessLevel, Department, User


@dataclass(frozen=True)
class DepartmentModuleAccess:
    can_access: bool
    is_pic: bool
    is_head: bool

    @property
    def can_review(self) -> bool:
        return self.is_head


def resolve_department_access(user: User, department: Department | None) -> DepartmentModuleAccess:
    if not user.is_active:
        return DepartmentModuleAccess(can_access=False, is_pic=False, is_head=False)
    if user.access_level == AccessLevel.administrator:
        return DepartmentModuleAccess(can_access=True, is_pic=False, is_head=False)
    if department is None:
        return DepartmentModuleAccess(can_access=False, is_pic=False, is_head=False)
    pics = getattr(department, "pics", ())
    is_pic = any(pic.id == user.id for pic in pics) or getattr(department, "pic_user_id", None) == user.id
    is_head = department.head_user_id == user.id
    return DepartmentModuleAccess(can_access=is_pic or is_head, is_pic=is_pic, is_head=is_head)


def resolve_department_membership(user: User, department: Department | None) -> DepartmentModuleAccess:
    if not user.is_active:
        return DepartmentModuleAccess(can_access=False, is_pic=False, is_head=False)
    if user.access_level == AccessLevel.administrator:
        return DepartmentModuleAccess(can_access=True, is_pic=False, is_head=False)
    if department is None:
        return DepartmentModuleAccess(can_access=False, is_pic=False, is_head=False)
    is_pic = any(pic.id == user.id for pic in getattr(department, "pics", ())) or (
        getattr(department, "pic_user_id", None) == user.id
    )
    is_head = department.head_user_id == user.id
    return DepartmentModuleAccess(
        can_access=user.department_code == department.code or is_pic or is_head,
        is_pic=is_pic,
        is_head=is_head,
    )


def ensure_department_access(access: DepartmentModuleAccess, department_name: str) -> None:
    if not access.can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the {department_name} PIC or Head can access this module",
        )


def ensure_department_head(access: DepartmentModuleAccess, department_name: str) -> None:
    if not access.is_head:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the {department_name} Head can review this transaction",
        )
