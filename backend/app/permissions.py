from fastapi import HTTPException, status

from app.models import AccessLevel, User


def can_manage_department(user: User, department_code: str | None) -> bool:
    if user.access_level == AccessLevel.administrator:
        return True
    return (
        user.access_level == AccessLevel.head
        and user.department_code is not None
        and user.department_code == department_code
    )


def ensure_can_manage(user: User, department_code: str | None) -> None:
    if not can_manage_department(user, department_code):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the department head or administrator can edit this submitted data",
        )


def ensure_can_assign_access(actor: User, access_level: AccessLevel) -> None:
    if access_level == AccessLevel.administrator and actor.access_level != AccessLevel.administrator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can assign administrator access",
        )
