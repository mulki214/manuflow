import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.master_data_services import apply_changes, generate_plant_code, generate_sequential_code
from app.models import (
    AccessLevel,
    BillOfMaterialItem,
    Corporation,
    Department,
    Machine,
    Plant,
    Product,
    ProductCategory,
    ProductLot,
    StorageLocation,
    Transportation,
    User,
    WarehouseStorage,
    WorkflowStatus,
)
from app.permissions import can_manage_department, ensure_can_manage
from app.qr_services import parse_product_qr
from app.sales_order_services import bom_would_create_cycle
from app.schemas import (
    BillOfMaterialItemResponse,
    BillOfMaterialReplace,
    BillOfMaterialResponse,
    CorporationCreate,
    CorporationResponse,
    CorporationUpdate,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    MachineCreate,
    MachineResponse,
    MachineUpdate,
    PaginatedCorporations,
    PaginatedDepartments,
    PaginatedMachines,
    PaginatedPlants,
    PaginatedProducts,
    PaginatedStorageLocations,
    PaginatedTransportations,
    PaginatedWarehouseStorages,
    PlantCreate,
    PlantResponse,
    PlantUpdate,
    ProductCreate,
    ProductQrResolveResponse,
    ProductResponse,
    ProductUpdate,
    StorageLocationCreate,
    StorageLocationResponse,
    StorageLocationUpdate,
    TransportationCreate,
    TransportationResponse,
    TransportationUpdate,
    WarehouseStorageCreate,
    WarehouseStorageResponse,
    WarehouseStorageUpdate,
)

router = APIRouter(
    prefix="/master-data",
    tags=["Master Data"],
    dependencies=[Depends(get_current_user)],
)


def not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found")


def conflict_error(exc: IntegrityError, fallback: str) -> HTTPException:
    message = str(exc.orig).lower()
    if "npwp" in message:
        detail = "NPWP is already registered"
    elif "foreign key" in message:
        detail = "Data is still referenced and cannot be deleted"
    elif "name" in message:
        detail = "Name is already registered"
    else:
        detail = fallback
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def paginated_result(
    db: AsyncSession, model: Any, filters: list[Any], page: int, size: int
) -> tuple[list[Any], int]:
    query = select(model).where(*filters).order_by(model.created_at.desc())
    items = (await db.execute(query.offset((page - 1) * size).limit(size))).scalars().all()
    total = (await db.execute(select(func.count()).select_from(model).where(*filters))).scalar_one()
    return list(items), total


async def commit_create(db: AsyncSession, record: Any, conflict_message: str) -> Any:
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
        return record
    except IntegrityError as exc:
        await db.rollback()
        raise conflict_error(exc, conflict_message) from exc


async def commit_update(db: AsyncSession, record: Any, conflict_message: str) -> Any:
    try:
        await db.commit()
        await db.refresh(record)
        return record
    except IntegrityError as exc:
        await db.rollback()
        raise conflict_error(exc, conflict_message) from exc


async def commit_delete(db: AsyncSession, record: Any) -> Response:
    try:
        await db.delete(record)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except IntegrityError as exc:
        await db.rollback()
        raise conflict_error(exc, "Data cannot be deleted") from exc


def workflow_values(record: Any, actor: User) -> dict[str, Any]:
    department_code = getattr(record, "department_code", None) or getattr(record, "owner_department_code", None)
    allowed = can_manage_department(actor, department_code)
    return {
        "department_code": department_code,
        "created_by": record.created_by,
        "workflow_status": record.workflow_status,
        "can_edit": allowed,
        "can_delete": allowed,
    }


def submitted_values(actor: User) -> dict[str, Any]:
    return {
        "department_code": actor.department_code,
        "created_by": actor.id,
        "workflow_status": WorkflowStatus.submitted,
    }


async def require_active_user(db: AsyncSession, user_id: str | None, label: str) -> User | None:
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Selected {label} must be an active user",
        )
    return user


async def require_department(db: AsyncSession, code: str | None) -> Department | None:
    if code is None:
        return None
    department = await db.get(Department, code)
    if not department:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Department not found")
    return department


async def department_response(db: AsyncSession, record: Department, actor: User) -> DepartmentResponse:
    pics = list(record.pics)
    head = await db.get(User, record.head_user_id) if record.head_user_id else None
    return DepartmentResponse(
        code=record.code,
        name=record.name,
        pic_user_id=pics[0].id if pics else None,
        pic_user_ids=[pic.id for pic in pics],
        head_user_id=record.head_user_id,
        pic_name=f"{pics[0].first_name} {pics[0].last_name}".strip() if pics else None,
        pic_names=[f"{pic.first_name} {pic.last_name}".strip() for pic in pics],
        head_name=f"{head.first_name} {head.last_name}".strip() if head else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
        **workflow_values(record, actor),
    )


async def synchronize_department_people(db: AsyncSession, record: Department) -> None:
    head = await db.get(User, record.head_user_id) if record.head_user_id else None
    for pic in record.pics:
        if pic.access_level != AccessLevel.administrator:
            pic.department_code = record.code
    if head and head.access_level != AccessLevel.administrator:
        head.department_code = record.code
        head.access_level = AccessLevel.head
    await db.commit()


def corporation_response(record: Corporation, actor: User) -> CorporationResponse:
    return CorporationResponse.model_validate(
        {**CorporationResponse.model_validate(record).model_dump(), **workflow_values(record, actor)}
    )


def plant_response(record: Plant, actor: User) -> PlantResponse:
    return PlantResponse.model_validate(
        {**PlantResponse.model_validate(record).model_dump(), **workflow_values(record, actor)}
    )


async def product_response(db: AsyncSession, record: Product, actor: User) -> ProductResponse:
    customer = await db.get(Corporation, record.customer_code)
    supplier = await db.get(Corporation, record.supplier_code) if record.supplier_code else None
    data = {
        key: getattr(record, key)
        for key in (
            "code",
            "customer_code",
            "supplier_code",
            "supply_source",
            "part_name",
            "part_no",
            "description",
            "gross_weight",
            "nett_weight",
            "current_stock_grams",
            "category",
            "created_at",
            "updated_at",
        )
    }
    stock_rows = await db.execute(
        select(ProductLot.unit, func.coalesce(func.sum(ProductLot.current_quantity_grams), 0))
        .where(ProductLot.product_code == record.code)
        .group_by(ProductLot.unit)
    )
    return ProductResponse(
        **data,
        customer_name=customer.name if customer else record.customer_code,
        supplier_name=supplier.name if supplier else None,
        stock_by_unit={unit: quantity for unit, quantity in stock_rows.all()},
        **workflow_values(record, actor),
    )


@router.get("/products/{product_code}/bom", response_model=BillOfMaterialResponse)
async def get_product_bom(
    product_code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BillOfMaterialResponse:
    product = await db.get(Product, product_code)
    if not product:
        raise not_found("Product")
    records = list(
        (
            await db.execute(
                select(BillOfMaterialItem)
                .where(BillOfMaterialItem.finished_product_code == product_code)
                .order_by(BillOfMaterialItem.id)
            )
        )
        .scalars()
        .all()
    )
    items = []
    for record in records:
        material = await db.get(Product, record.material_product_code)
        items.append(
            BillOfMaterialItemResponse(
                id=record.id,
                material_product_code=record.material_product_code,
                material_description=material.description if material else record.material_product_code,
                quantity=record.quantity,
                unit=record.unit,
                is_active=record.is_active,
            )
        )
    return BillOfMaterialResponse(finished_product_code=product_code, items=items)


@router.put("/products/{product_code}/bom", response_model=BillOfMaterialResponse)
async def replace_product_bom(
    product_code: str,
    data: BillOfMaterialReplace,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BillOfMaterialResponse:
    product = await db.get(Product, product_code)
    if not product:
        raise not_found("Product")
    if product.category not in {ProductCategory.work_in_progress, ProductCategory.finished_good}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="BOM can only be configured for a Work In Progress or Finished Good",
        )
    ensure_can_manage(current_user, product.department_code)
    for item in data.items:
        material = await db.get(Product, item.material_product_code)
        if not material or material.category == ProductCategory.finished_good:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="BOM material must be a non-finished-good Product",
            )
    active_bom_rows = list(
        (
            await db.execute(select(BillOfMaterialItem).where(BillOfMaterialItem.is_active.is_(True)))
        )
        .scalars()
        .all()
    )
    if bom_would_create_cycle(
        product_code, (item.material_product_code for item in data.items), active_bom_rows
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="BOM cannot contain a circular WIP dependency",
        )
    existing = list(
        (await db.execute(select(BillOfMaterialItem).where(BillOfMaterialItem.finished_product_code == product_code)))
        .scalars()
        .all()
    )
    for record in existing:
        await db.delete(record)
    for item in data.items:
        db.add(
            BillOfMaterialItem(
                finished_product_code=product_code,
                material_product_code=item.material_product_code,
                quantity=item.quantity,
                unit=item.unit.value,
            )
        )
    await db.commit()
    return await get_product_bom(product_code, db, current_user)


async def machine_response(db: AsyncSession, record: Machine, actor: User) -> MachineResponse:
    plant = await db.get(Plant, record.plant_code)
    data = {
        key: getattr(record, key)
        for key in (
            "code",
            "name",
            "specification",
            "machine_type",
            "year",
            "country_of_origin",
            "plant_code",
            "created_at",
            "updated_at",
        )
    }
    return MachineResponse(
        **data,
        plant_name=plant.name if plant else record.plant_code,
        **workflow_values(record, actor),
    )


async def storage_location_response(db: AsyncSession, record: StorageLocation, actor: User) -> StorageLocationResponse:
    plant = await db.get(Plant, record.plant_code)
    storage = await db.get(WarehouseStorage, record.storage_code)
    return StorageLocationResponse(
        code=record.code,
        name=record.name,
        plant_code=record.plant_code,
        plant_name=plant.name if plant else record.plant_code,
        storage_code=record.storage_code,
        storage_name=storage.name if storage else record.storage_code,
        storage_type=storage.storage_type if storage else "general",
        description=record.description,
        created_at=record.created_at,
        updated_at=record.updated_at,
        **workflow_values(record, actor),
    )


async def warehouse_storage_response(
    db: AsyncSession, record: WarehouseStorage, actor: User
) -> WarehouseStorageResponse:
    plant = await db.get(Plant, record.plant_code)
    return WarehouseStorageResponse(
        code=record.code,
        name=record.name,
        storage_type=record.storage_type,
        plant_code=record.plant_code,
        plant_name=plant.name if plant else record.plant_code,
        description=record.description,
        created_at=record.created_at,
        updated_at=record.updated_at,
        **workflow_values(record, actor),
    )


def transportation_response(record: Transportation, actor: User) -> TransportationResponse:
    return TransportationResponse.model_validate(
        {**TransportationResponse.model_validate(record).model_dump(), **workflow_values(record, actor)}
    )


async def require_storage(db: AsyncSession, code: str, plant_code: str | None = None) -> WarehouseStorage:
    storage = await db.get(WarehouseStorage, code)
    if not storage or (plant_code is not None and storage.plant_code != plant_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected Storage must belong to the selected Plant",
        )
    return storage


async def require_corporation_role(db: AsyncSession, code: str, role: str) -> Corporation:
    corporation = await db.get(Corporation, code)
    valid = corporation and (
        (role == "customer" and corporation.is_customer) or (role == "supplier" and corporation.is_supplier)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Selected corporation is not a {role}",
        )
    return corporation


async def require_plant(db: AsyncSession, code: str) -> Plant:
    plant = await db.get(Plant, code)
    if not plant:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected plant does not exist")
    return plant


@router.get("/departments", response_model=PaginatedDepartments)
async def list_departments(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedDepartments:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Department.code.ilike(term), Department.name.ilike(term)))
    items, total = await paginated_result(db, Department, filters, page, size)
    return PaginatedDepartments(
        items=[await department_response(db, item, current_user) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentResponse:
    pics = [await require_active_user(db, user_id, "PIC") for user_id in data.pic_user_ids]
    await require_active_user(db, data.head_user_id, "Head")
    record = Department(
        code=await generate_sequential_code(db, "department", data.name),
        name=data.name,
        pic_user_id=data.pic_user_ids[0],
        head_user_id=data.head_user_id,
        owner_department_code=current_user.department_code,
        created_by=current_user.id,
        workflow_status=WorkflowStatus.submitted,
    )
    record.pics = [pic for pic in pics if pic is not None]
    await commit_create(db, record, "Department code or name already exists")
    await synchronize_department_people(db, record)
    return await department_response(db, record, current_user)


@router.get("/departments/{code}", response_model=DepartmentResponse)
async def get_department(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentResponse:
    record = await db.get(Department, code)
    if not record:
        raise not_found("Department")
    return await department_response(db, record, current_user)


@router.patch("/departments/{code}", response_model=DepartmentResponse)
async def update_department(
    code: str,
    data: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentResponse:
    record = await db.get(Department, code)
    if not record:
        raise not_found("Department")
    ensure_can_manage(current_user, record.owner_department_code)
    changes = data.model_dump(exclude_unset=True)
    pic_user_ids = changes.pop("pic_user_ids", None)
    if pic_user_ids is not None:
        pics = [await require_active_user(db, user_id, "PIC") for user_id in pic_user_ids]
        record.pics = [pic for pic in pics if pic is not None]
        record.pic_user_id = pic_user_ids[0]
    if "head_user_id" in changes:
        await require_active_user(db, changes["head_user_id"], "Head")
    apply_changes(record, changes)
    await commit_update(db, record, "Department name already exists")
    await synchronize_department_people(db, record)
    return await department_response(db, record, current_user)


@router.delete("/departments/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    record = await db.get(Department, code)
    if not record:
        raise not_found("Department")
    if record.code in {"GENERAL", "PURCHASING", "SALES", "WAREHOUSE"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System departments cannot be deleted",
        )
    ensure_can_manage(current_user, record.owner_department_code)
    return await commit_delete(db, record)


@router.get("/corporations", response_model=PaginatedCorporations)
async def list_corporations(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    customer_only: bool = False,
    supplier_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedCorporations:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Corporation.code.ilike(term), Corporation.name.ilike(term)))
    if customer_only:
        filters.append(Corporation.is_customer.is_(True))
    if supplier_only:
        filters.append(Corporation.is_supplier.is_(True))
    items, total = await paginated_result(db, Corporation, filters, page, size)
    return PaginatedCorporations(
        items=[corporation_response(item, current_user) for item in items], total=total, page=page, size=size
    )


@router.post("/corporations", response_model=CorporationResponse, status_code=status.HTTP_201_CREATED)
async def create_corporation(
    data: CorporationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorporationResponse:
    record = Corporation(
        code=await generate_sequential_code(db, "corporation", data.name),
        **data.model_dump(),
        **submitted_values(current_user),
    )
    await commit_create(db, record, "Corporation code or NPWP already exists")
    return corporation_response(record, current_user)


@router.get("/corporations/{code}", response_model=CorporationResponse)
async def get_corporation(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> CorporationResponse:
    record = await db.get(Corporation, code)
    if not record:
        raise not_found("Corporation")
    return corporation_response(record, current_user)


@router.patch("/corporations/{code}", response_model=CorporationResponse)
async def update_corporation(
    code: str,
    data: CorporationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorporationResponse:
    record = await db.get(Corporation, code)
    if not record:
        raise not_found("Corporation")
    ensure_can_manage(current_user, record.department_code)
    changes = data.model_dump(exclude_unset=True)
    if not changes.get("is_customer", record.is_customer) and not changes.get("is_supplier", record.is_supplier):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Corporation must be a customer, supplier, or both",
        )
    apply_changes(record, changes)
    await commit_update(db, record, "NPWP is already registered")
    return corporation_response(record, current_user)


@router.delete("/corporations/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_corporation(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Response:
    record = await db.get(Corporation, code)
    if not record:
        raise not_found("Corporation")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)


@router.get("/plants", response_model=PaginatedPlants)
async def list_plants(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedPlants:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Plant.code.ilike(term), Plant.name.ilike(term)))
    items, total = await paginated_result(db, Plant, filters, page, size)
    return PaginatedPlants(
        items=[plant_response(item, current_user) for item in items], total=total, page=page, size=size
    )


@router.post("/plants", response_model=PlantResponse, status_code=status.HTTP_201_CREATED)
async def create_plant(
    data: PlantCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> PlantResponse:
    record = Plant(code=await generate_plant_code(db), **data.model_dump(), **submitted_values(current_user))
    await commit_create(db, record, "Plant code already exists")
    return plant_response(record, current_user)


@router.get("/plants/{code}", response_model=PlantResponse)
async def get_plant(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> PlantResponse:
    record = await db.get(Plant, code)
    if not record:
        raise not_found("Plant")
    return plant_response(record, current_user)


@router.patch("/plants/{code}", response_model=PlantResponse)
async def update_plant(
    code: str,
    data: PlantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlantResponse:
    record = await db.get(Plant, code)
    if not record:
        raise not_found("Plant")
    ensure_can_manage(current_user, record.department_code)
    apply_changes(record, data.model_dump(exclude_unset=True))
    await commit_update(db, record, "Plant could not be updated")
    return plant_response(record, current_user)


@router.delete("/plants/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plant(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Response:
    record = await db.get(Plant, code)
    if not record:
        raise not_found("Plant")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)


@router.get("/warehouse-storages", response_model=PaginatedWarehouseStorages)
async def list_warehouse_storages(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedWarehouseStorages:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(WarehouseStorage.code.ilike(term), WarehouseStorage.name.ilike(term)))
    if plant_code:
        filters.append(WarehouseStorage.plant_code == plant_code)
    items, total = await paginated_result(db, WarehouseStorage, filters, page, size)
    return PaginatedWarehouseStorages(
        items=[await warehouse_storage_response(db, item, current_user) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/warehouse-storages", response_model=WarehouseStorageResponse, status_code=status.HTTP_201_CREATED)
async def create_warehouse_storage(
    data: WarehouseStorageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarehouseStorageResponse:
    await require_plant(db, data.plant_code)
    record = WarehouseStorage(
        code=await generate_sequential_code(db, "warehouse_storage", data.name),
        **data.model_dump(),
        **submitted_values(current_user),
    )
    await commit_create(db, record, "Storage code already exists")
    return await warehouse_storage_response(db, record, current_user)


@router.patch("/warehouse-storages/{code}", response_model=WarehouseStorageResponse)
async def update_warehouse_storage(
    code: str,
    data: WarehouseStorageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarehouseStorageResponse:
    record = await db.get(WarehouseStorage, code)
    if not record:
        raise not_found("Storage")
    ensure_can_manage(current_user, record.department_code)
    changes = data.model_dump(exclude_unset=True)
    if "plant_code" in changes:
        await require_plant(db, changes["plant_code"])
    apply_changes(record, changes)
    await commit_update(db, record, "Storage could not be updated")
    return await warehouse_storage_response(db, record, current_user)


@router.delete("/warehouse-storages/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse_storage(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    record = await db.get(WarehouseStorage, code)
    if not record:
        raise not_found("Storage")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)


@router.get("/transportations", response_model=PaginatedTransportations)
async def list_transportations(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedTransportations:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Transportation.code.ilike(term), Transportation.vehicle_number.ilike(term)))
    if active_only:
        filters.append(Transportation.is_active.is_(True))
    items, total = await paginated_result(db, Transportation, filters, page, size)
    return PaginatedTransportations(
        items=[transportation_response(item, current_user) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/transportations", response_model=TransportationResponse, status_code=status.HTTP_201_CREATED)
async def create_transportation(
    data: TransportationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransportationResponse:
    record = Transportation(
        code=await generate_sequential_code(db, "transportation", data.vehicle_number),
        **data.model_dump(),
        **submitted_values(current_user),
    )
    await commit_create(db, record, "Vehicle Number already exists")
    return transportation_response(record, current_user)


@router.patch("/transportations/{code}", response_model=TransportationResponse)
async def update_transportation(
    code: str,
    data: TransportationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransportationResponse:
    record = await db.get(Transportation, code)
    if not record:
        raise not_found("Transportation")
    ensure_can_manage(current_user, record.department_code)
    apply_changes(record, data.model_dump(exclude_unset=True))
    await commit_update(db, record, "Vehicle Number already exists")
    return transportation_response(record, current_user)


@router.delete("/transportations/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transportation(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    record = await db.get(Transportation, code)
    if not record:
        raise not_found("Transportation")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)


@router.get("/storage-locations", response_model=PaginatedStorageLocations)
async def list_storage_locations(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedStorageLocations:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(StorageLocation.code.ilike(term), StorageLocation.name.ilike(term)))
    if plant_code:
        filters.append(StorageLocation.plant_code == plant_code)
    items, total = await paginated_result(db, StorageLocation, filters, page, size)
    return PaginatedStorageLocations(
        items=[await storage_location_response(db, item, current_user) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/storage-locations", response_model=StorageLocationResponse, status_code=status.HTTP_201_CREATED)
async def create_storage_location(
    data: StorageLocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageLocationResponse:
    await require_plant(db, data.plant_code)
    await require_storage(db, data.storage_code, data.plant_code)
    record = StorageLocation(
        code=await generate_sequential_code(db, "storage_location", data.name),
        **data.model_dump(),
        **submitted_values(current_user),
    )
    await commit_create(db, record, "Storage Location code already exists")
    return await storage_location_response(db, record, current_user)


@router.get("/storage-locations/{code}", response_model=StorageLocationResponse)
async def get_storage_location(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageLocationResponse:
    record = await db.get(StorageLocation, code)
    if not record:
        raise not_found("Storage Location")
    return await storage_location_response(db, record, current_user)


@router.patch("/storage-locations/{code}", response_model=StorageLocationResponse)
async def update_storage_location(
    code: str,
    data: StorageLocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageLocationResponse:
    record = await db.get(StorageLocation, code)
    if not record:
        raise not_found("Storage Location")
    ensure_can_manage(current_user, record.department_code)
    changes = data.model_dump(exclude_unset=True)
    if "plant_code" in changes:
        await require_plant(db, changes["plant_code"])
    target_plant = changes.get("plant_code", record.plant_code)
    target_storage = changes.get("storage_code", record.storage_code)
    await require_storage(db, target_storage, target_plant)
    apply_changes(record, changes)
    await commit_update(db, record, "Storage Location could not be updated")
    return await storage_location_response(db, record, current_user)


@router.delete("/storage-locations/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_storage_location(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    record = await db.get(StorageLocation, code)
    if not record:
        raise not_found("Storage Location")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)


@router.get("/products", response_model=PaginatedProducts)
async def list_products(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    supplier_code: str | None = None,
    customer_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedProducts:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Product.code.ilike(term), Product.part_name.ilike(term)))
    if supplier_code:
        filters.append(Product.supplier_code == supplier_code)
    if customer_code:
        filters.append(Product.customer_code == customer_code)
    items, total = await paginated_result(db, Product, filters, page, size)
    return PaginatedProducts(
        items=[await product_response(db, item, current_user) for item in items], total=total, page=page, size=size
    )


@router.get("/products/qr-resolve", response_model=ProductQrResolveResponse)
async def resolve_product_qr(
    payload: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductQrResolveResponse:
    try:
        product_code, lot_number = parse_product_qr(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    product = await db.get(Product, product_code)
    if not product:
        raise not_found("Product")
    lot = None
    if lot_number:
        lot = (
            await db.execute(
                select(ProductLot)
                .where(ProductLot.product_code == product.code, ProductLot.lot_number == lot_number)
                .order_by(ProductLot.id.desc())
            )
        ).scalars().first()
        if not lot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product lot not found")
    return ProductQrResolveResponse(
        product_code=product.code,
        product_name=product.part_name,
        description=product.description,
        lot_id=lot.id if lot else None,
        lot_number=lot.lot_number if lot else None,
        unit=lot.unit if lot else None,
        available_quantity=lot.current_quantity_grams if lot else None,
    )


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProductResponse:
    await require_corporation_role(db, data.customer_code, "customer")
    if data.supplier_code:
        await require_corporation_role(db, data.supplier_code, "supplier")
    record = Product(
        code=await generate_sequential_code(db, "product", data.part_name),
        **data.model_dump(),
        **submitted_values(current_user),
    )
    await commit_create(db, record, "Product code already exists")
    return await product_response(db, record, current_user)


@router.get("/products/{code}", response_model=ProductResponse)
async def get_product(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProductResponse:
    record = await db.get(Product, code)
    if not record:
        raise not_found("Product")
    return await product_response(db, record, current_user)


@router.patch("/products/{code}", response_model=ProductResponse)
async def update_product(
    code: str,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductResponse:
    record = await db.get(Product, code)
    if not record:
        raise not_found("Product")
    ensure_can_manage(current_user, record.department_code)
    changes = data.model_dump(exclude_unset=True)
    if "customer_code" in changes:
        await require_corporation_role(db, changes["customer_code"], "customer")
    if "supplier_code" in changes and changes["supplier_code"]:
        await require_corporation_role(db, changes["supplier_code"], "supplier")
    supply_source = changes.get("supply_source", record.supply_source)
    if supply_source.value == "manufactured_internally":
        changes["supplier_code"] = None
    elif not changes.get("supplier_code", record.supplier_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supplier is required for external products",
        )
    if changes.get("description") is not None and not changes["description"].strip():
        changes["description"] = (
            f"{changes.get('part_name', record.part_name)} {changes.get('part_no', record.part_no)}"
        )
    apply_changes(record, changes)
    await commit_update(db, record, "Product could not be updated")
    return await product_response(db, record, current_user)


@router.delete("/products/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Response:
    record = await db.get(Product, code)
    if not record:
        raise not_found("Product")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)


@router.get("/machines", response_model=PaginatedMachines)
async def list_machines(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedMachines:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Machine.code.ilike(term), Machine.name.ilike(term)))
    items, total = await paginated_result(db, Machine, filters, page, size)
    return PaginatedMachines(
        items=[await machine_response(db, item, current_user) for item in items], total=total, page=page, size=size
    )


@router.post("/machines", response_model=MachineResponse, status_code=status.HTTP_201_CREATED)
async def create_machine(
    data: MachineCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> MachineResponse:
    await require_plant(db, data.plant_code)
    record = Machine(
        code=await generate_sequential_code(db, "machine", data.name),
        **data.model_dump(),
        **submitted_values(current_user),
    )
    await commit_create(db, record, "Machine code already exists")
    return await machine_response(db, record, current_user)


@router.get("/machines/{code}", response_model=MachineResponse)
async def get_machine(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> MachineResponse:
    record = await db.get(Machine, code)
    if not record:
        raise not_found("Machine")
    return await machine_response(db, record, current_user)


@router.patch("/machines/{code}", response_model=MachineResponse)
async def update_machine(
    code: str,
    data: MachineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MachineResponse:
    record = await db.get(Machine, code)
    if not record:
        raise not_found("Machine")
    ensure_can_manage(current_user, record.department_code)
    changes = data.model_dump(exclude_unset=True)
    if "plant_code" in changes:
        await require_plant(db, changes["plant_code"])
    apply_changes(record, changes)
    await commit_update(db, record, "Machine could not be updated")
    return await machine_response(db, record, current_user)


@router.delete("/machines/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine(
    code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Response:
    record = await db.get(Machine, code)
    if not record:
        raise not_found("Machine")
    ensure_can_manage(current_user, record.department_code)
    return await commit_delete(db, record)
