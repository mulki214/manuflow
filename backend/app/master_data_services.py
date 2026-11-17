import re
import secrets
import string

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BillOfMaterialItem, CodeSequence, Plant


def build_initials(name: str, max_length: int = 12) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    initials = "".join(word[0] for word in words)[:max_length]
    if not initials:
        raise ValueError("Name must contain at least one alphanumeric character")
    return initials


def format_sequential_code(prefix: str, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Code sequence must be between 000 and 999")
    return prefix if sequence == 0 else f"{prefix}{sequence:03d}"


async def generate_sequential_code(db: AsyncSession, entity: str, name: str) -> str:
    prefix = build_initials(name)
    statement = (
        insert(CodeSequence)
        .values(entity=entity, prefix=prefix, last_value=0)
        .on_conflict_do_update(
            index_elements=[CodeSequence.entity, CodeSequence.prefix],
            set_={"last_value": CodeSequence.last_value + 1},
        )
        .returning(CodeSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    return format_sequential_code(prefix, sequence)


def random_plant_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(5))


async def generate_plant_code(db: AsyncSession) -> str:
    for _ in range(25):
        code = random_plant_code()
        if not await db.scalar(select(Plant.code).where(Plant.code == code)):
            return code
    raise ValueError("Unable to generate a unique plant code")


def apply_changes(record: object, changes: dict) -> None:
    for field, value in changes.items():
        setattr(record, field, value)


def reconcile_bom_items(
    finished_product_code: str,
    existing_items: list[BillOfMaterialItem],
    requested_items: list[object],
) -> tuple[list[BillOfMaterialItem], list[BillOfMaterialItem]]:
    """Update BOM rows in place where possible, avoiding transient unique-key collisions."""
    existing_by_material = {record.material_product_code: record for record in existing_items}
    requested_by_material = {item.material_product_code: item for item in requested_items}

    additions: list[BillOfMaterialItem] = []
    for material_code, item in requested_by_material.items():
        record = existing_by_material.get(material_code)
        if record is not None:
            record.quantity = item.quantity
            record.unit = item.unit.value
            record.is_active = True
            continue
        additions.append(
            BillOfMaterialItem(
                finished_product_code=finished_product_code,
                material_product_code=material_code,
                quantity=item.quantity,
                unit=item.unit.value,
            )
        )

    removals = [record for record in existing_items if record.material_product_code not in requested_by_material]
    return additions, removals
