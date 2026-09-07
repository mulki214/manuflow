from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AccessLevel, Department, User
from app.permissions import can_manage_department, ensure_can_assign_access, ensure_can_manage
from app.schemas import PasswordChangeRequest, UserCreate, UserListResponse, UserResponse, UserUpdate
from app.security import hash_password, verify_password
from app.services import create_user, update_user

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(get_current_user)])


def conflict_error(exc: IntegrityError) -> HTTPException:
    message = str(exc.orig).lower()
    detail = "Email atau nomor KTP sudah digunakan"
    if "email" in message:
        detail = "Email sudah digunakan"
    elif "ktp" in message:
        detail = "Nomor KTP sudah digunakan"
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def validate_department(db: AsyncSession, department_code: str | None) -> Department | None:
    if department_code is None:
        return None
    department = await db.get(Department, department_code)
    if not department:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Department not found")
    return department


async def user_response(db: AsyncSession, user: User, actor: User) -> UserResponse:
    data = UserResponse.model_validate(user).model_dump()
    department = await db.get(Department, user.department_code) if user.department_code else None
    pics = list(department.pics) if department else []
    head = await db.get(User, department.head_user_id) if department and department.head_user_id else None
    allowed = can_manage_department(actor, user.department_code)
    data.update(
        department_name=department.name if department else None,
        pic_user_id=pics[0].id if pics else None,
        pic_name=f"{pics[0].first_name} {pics[0].last_name}".strip() if pics else None,
        pic_user_ids=[pic.id for pic in pics],
        pic_names=[f"{pic.first_name} {pic.last_name}".strip() for pic in pics],
        head_user_id=head.id if head else None,
        head_name=f"{head.first_name} {head.last_name}".strip() if head else None,
        can_edit=allowed,
        can_delete=allowed and actor.id != user.id,
    )
    return UserResponse(**data)


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserListResponse:
    filters = [] if include_inactive else [User.is_active.is_(True)]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
                User.id.ilike(term),
            )
        )
    query = select(User).where(*filters)
    items = (
        (await db.execute(query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size))).scalars().all()
    )
    total = (await db.execute(select(func.count()).select_from(User).where(*filters))).scalar_one()
    responses = [await user_response(db, user, current_user) for user in items]
    return UserListResponse(items=responses, total=total, page=page, size=size)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def add_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    await validate_department(db, data.department_code)
    ensure_can_assign_access(current_user, data.access_level)
    if current_user.access_level != AccessLevel.administrator and data.department_code != current_user.department_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff and heads can only submit users for their own department",
        )
    try:
        user = await create_user(db, data)
        return await user_response(db, user, current_user)
    except IntegrityError as exc:
        await db.rollback()
        raise conflict_error(exc) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan")
    return await user_response(db, user, current_user)


@router.patch("/{user_id}", response_model=UserResponse)
async def edit_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan")
    ensure_can_manage(current_user, user.department_code)
    changes = data.model_dump(exclude_unset=True)
    if "department_code" in changes:
        await validate_department(db, changes["department_code"])
        if (
            current_user.access_level != AccessLevel.administrator
            and changes["department_code"] != current_user.department_code
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Cannot move a user to another department"
            )
    if "access_level" in changes:
        ensure_can_assign_access(current_user, changes["access_level"])
    try:
        updated = await update_user(db, user, data)
        return await user_response(db, updated, current_user)
    except IntegrityError as exc:
        await db.rollback()
        raise conflict_error(exc) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tidak dapat menonaktifkan akun sendiri")
    ensure_can_manage(current_user, user.department_code)
    user.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_own_password(
    data: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
