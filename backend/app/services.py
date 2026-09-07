from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyUserSequence, User
from app.schemas import UserCreate, UserUpdate
from app.security import hash_password


def format_user_id(creation_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Nomor urut user harus berada di antara 000 dan 999")
    return f"{creation_date:%d%m%y}{sequence:03d}"


async def generate_user_id(db: AsyncSession, creation_date: date | None = None) -> str:
    current_date = creation_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailyUserSequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyUserSequence.sequence_date],
            set_={"last_value": DailyUserSequence.last_value + 1},
        )
        .returning(DailyUserSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise ValueError("Batas 999 user per hari telah tercapai")
    return format_user_id(current_date, sequence)


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        id=await generate_user_id(db),
        first_name=data.first_name,
        last_name=data.last_name,
        email=str(data.email).lower(),
        gender=data.gender,
        role=data.role,
        department_code=data.department_code,
        access_level=data.access_level,
        ktp_number=data.ktp_number,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    changes = data.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
    for field, value in changes.items():
        setattr(user, field, value)
    if password:
        user.password_hash = hash_password(password)
    await db.commit()
    await db.refresh(user)
    return user
