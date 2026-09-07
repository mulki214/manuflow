import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import AccessLevel, Gender, User
from app.schemas import UserCreate
from app.services import create_user


async def seed() -> None:
    async with SessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == settings.first_admin_email.lower()))
        ).scalar_one_or_none()
        if existing:
            print(f"Admin {existing.email} already exists")
            return
        admin = await create_user(
            db,
            UserCreate(
                first_name=settings.first_admin_first_name,
                last_name=settings.first_admin_last_name,
                email=settings.first_admin_email,
                gender=Gender.male,
                role="Administrator",
                department_code="GENERAL",
                access_level=AccessLevel.administrator,
                ktp_number="0000000000000000",
                password=settings.first_admin_password,
            ),
        )
        print(f"Created initial admin {admin.email} ({admin.id})")


if __name__ == "__main__":
    asyncio.run(seed())
