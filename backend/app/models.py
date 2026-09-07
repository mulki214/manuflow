import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Gender(str, enum.Enum):
    male = "male"
    female = "female"


class AccessLevel(str, enum.Enum):
    staff = "staff"
    head = "head"
    administrator = "administrator"


class WorkflowStatus(str, enum.Enum):
    submitted = "submitted"


class PurchaseOrderStatus(str, enum.Enum):
    waiting_review = "waiting_review"
    approved = "approved"
    rejected = "rejected"


class SalesOrderStatus(str, enum.Enum):
    waiting_review = "waiting_review"
    approved = "approved"
    rejected = "rejected"


class SalesOrderType(str, enum.Enum):
    mass_pro = "mass_pro"
    job_order = "job_order"
    trial = "trial"


class FulfillmentStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class UnitOfMeasure(str, enum.Enum):
    pcs = "pcs"
    bar = "bar"
    liter = "liter"
    pail = "pail"
    kg = "kg"
    gram = "gram"


class ProductCategory(str, enum.Enum):
    raw_material = "raw_material"
    work_in_progress = "work_in_progress"
    finished_good = "finished_good"


class ProductSupplySource(str, enum.Enum):
    external_supplier = "external_supplier"
    manufactured_internally = "manufactured_internally"


class FinishGoodStatus(str, enum.Enum):
    posted = "posted"
    reversed = "reversed"


class DeliveryStatus(str, enum.Enum):
    dispatched = "dispatched"
    delivered = "delivered"
    # Legacy documents posted before delivery confirmation existed.
    posted = "posted"
    reversed = "reversed"


class StorageType(str, enum.Enum):
    raw_material = "raw_material"
    work_in_progress = "work_in_progress"
    finished_goods = "finished_goods"
    general = "general"


class ReceivingSourceType(str, enum.Enum):
    supplier = "supplier"
    customer = "customer"


class ReceivingTransportSource(str, enum.Enum):
    external = "external"
    internal = "internal"


class ReceivingStatus(str, enum.Enum):
    posted = "posted"
    reversed = "reversed"


class InventoryMovementType(str, enum.Enum):
    receiving_in = "receiving_in"
    receiving_reversal = "receiving_reversal"
    stock_out = "stock_out"
    warehouse_out = "warehouse_out"
    warehouse_in = "warehouse_in"
    warehouse_reversal = "warehouse_reversal"


class ConsumableDispositionType(str, enum.Enum):
    consumed = "consumed"
    waste = "waste"
    scrap = "scrap"


class WarehouseDestinationType(str, enum.Enum):
    wip = "wip"
    finished_goods = "finished_goods"


class WarehouseTransferStatus(str, enum.Enum):
    posted = "posted"
    reversed = "reversed"


class WipProcessType(str, enum.Enum):
    production = "production"
    quality = "quality"
    repair = "repair"


class WipLotStatus(str, enum.Enum):
    queued = "queued"
    in_process = "in_process"
    awaiting_qc = "awaiting_qc"
    awaiting_finish_goods = "awaiting_finish_goods"
    repair_required = "repair_required"
    repair_in_process = "repair_in_process"
    ng = "ng"
    completed = "completed"
    reversed = "reversed"


department_pics = Table(
    "department_pics",
    Base.metadata,
    Column("department_code", ForeignKey("departments.code", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Department(Base):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    pic_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    head_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owner_department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pics: Mapped[list["User"]] = relationship(secondary=department_pics, lazy="selectin")


class DailyUserSequence(Base):
    __tablename__ = "daily_user_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyPurchaseOrderSequence(Base):
    __tablename__ = "daily_purchase_order_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailySalesOrderSequence(Base):
    __tablename__ = "daily_sales_order_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyReceivingSequence(Base):
    __tablename__ = "daily_receiving_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyWarehouseTransferSequence(Base):
    __tablename__ = "daily_warehouse_transfer_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(9), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender_enum"), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        Enum(AccessLevel, name="access_level_enum"), nullable=False, default=AccessLevel.staff
    )
    ktp_number: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CodeSequence(Base):
    __tablename__ = "code_sequences"

    entity: Mapped[str] = mapped_column(String(30), primary_key=True)
    prefix: Mapped[str] = mapped_column(String(12), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class Corporation(Base):
    __tablename__ = "corporations"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_person_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_person_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    npwp: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    is_customer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_supplier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Plant(Base):
    __tablename__ = "plants"

    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    full_address: Mapped[str] = mapped_column(Text, nullable=False)
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Product(Base):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    customer_code: Mapped[str] = mapped_column(
        ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_code: Mapped[str | None] = mapped_column(
        ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    supply_source: Mapped[ProductSupplySource] = mapped_column(
        Enum(ProductSupplySource, name="product_supply_source_enum"),
        nullable=False,
        default=ProductSupplySource.external_supplier,
        index=True,
    )
    part_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    part_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    gross_weight: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    nett_weight: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    current_stock_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    category: Mapped[ProductCategory] = mapped_column(
        Enum(ProductCategory, name="product_category_enum"),
        nullable=False,
        default=ProductCategory.finished_good,
        index=True,
    )
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Machine(Base):
    __tablename__ = "machines"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    specification: Mapped[str] = mapped_column(Text, nullable=False)
    machine_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    country_of_origin: Mapped[str] = mapped_column(String(100), nullable=False)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    po_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    supplier_code: Mapped[str] = mapped_column(
        ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_address: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_contact_person: Mapped[str] = mapped_column(String(150), nullable=False)
    quotation_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quotation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    delivery_plant_code: Mapped[str] = mapped_column(
        ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    delivery_plant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    payment_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IDR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    ppn_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    ppn_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    pph23_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    pph23_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, name="purchase_order_status_enum"),
        nullable=False,
        default=PurchaseOrderStatus.waiting_review,
        index=True,
    )
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        Enum(FulfillmentStatus, name="fulfillment_status_enum"),
        nullable=False,
        default=FulfillmentStatus.open,
        index=True,
    )
    department_code: Mapped[str] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderItem.line_number",
        lazy="selectin",
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_number: Mapped[str] = mapped_column(
        ForeignKey("purchase_orders.po_number", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_no: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="gram")
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    sales_order_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    po_receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_po_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_po_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    customer_code: Mapped[str] = mapped_column(
        ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bill_to_address: Mapped[str] = mapped_column(Text, nullable=False)
    bill_to_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    ship_to_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ship_to_address: Mapped[str] = mapped_column(Text, nullable=False)
    ship_to_contact_person: Mapped[str] = mapped_column(String(150), nullable=False)
    ship_to_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_type: Mapped[SalesOrderType] = mapped_column(
        Enum(SalesOrderType, name="sales_order_type_enum"), nullable=False, index=True
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IDR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[SalesOrderStatus] = mapped_column(
        Enum(SalesOrderStatus, name="sales_order_status_enum"),
        nullable=False,
        default=SalesOrderStatus.waiting_review,
        index=True,
    )
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        Enum(FulfillmentStatus, name="fulfillment_status_enum"),
        nullable=False,
        default=FulfillmentStatus.open,
        index=True,
    )
    department_code: Mapped[str] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan",
        order_by="SalesOrderItem.line_number",
        lazy="selectin",
    )


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sales_order_number: Mapped[str] = mapped_column(
        ForeignKey("sales_orders.sales_order_number", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)
    part_no: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="gram")
    material_received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    delivered_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    outstanding_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")

    sales_order: Mapped[SalesOrder] = relationship(back_populates="items")
    material_allocations: Mapped[list["SalesOrderMaterialAllocation"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class SalesOrderMaterialAllocation(Base):
    """BOM material reserved for a finished-good Sales Order item."""

    __tablename__ = "sales_order_material_allocations"
    __table_args__ = (UniqueConstraint("sales_order_item_id", "material_product_code", name="uq_so_item_material"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sales_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StorageLocation(Base):
    __tablename__ = "storage_locations"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    storage_code: Mapped[str | None] = mapped_column(
        ForeignKey("warehouse_storages.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WarehouseStorage(Base):
    __tablename__ = "warehouse_storages"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    storage_type: Mapped[StorageType] = mapped_column(
        Enum(StorageType, name="storage_type_enum"), nullable=False, index=True
    )
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Transportation(Base):
    __tablename__ = "transportations"

    code: Mapped[str] = mapped_column(String(15), primary_key=True)
    vehicle_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(100), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manufacturing_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carrier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("departments.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"), nullable=False, default=WorkflowStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WipProcess(Base):
    __tablename__ = "wip_processes"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    process_type: Mapped[WipProcessType] = mapped_column(
        Enum(WipProcessType, name="wip_process_type_enum"), nullable=False, index=True
    )
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProductProcessStandard(Base):
    __tablename__ = "product_process_standards"
    __table_args__ = (
        UniqueConstraint("product_code", "process_code", "machine_code", name="uq_product_process_standard"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"), index=True)
    process_code: Mapped[str] = mapped_column(ForeignKey("wip_processes.code", ondelete="CASCADE"), index=True)
    machine_code: Mapped[str | None] = mapped_column(ForeignKey("machines.code", ondelete="SET NULL"), nullable=True)
    working_hours: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    expected_output_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    output_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    target_cycle_time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    maximum_ng_quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 3), nullable=True)
    maximum_ng_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RepairRoute(Base):
    __tablename__ = "repair_routes"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"), index=True)
    source_process_code: Mapped[str] = mapped_column(ForeignKey("wip_processes.code", ondelete="RESTRICT"))
    return_process_code: Mapped[str | None] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RepairRouteStep(Base):
    __tablename__ = "repair_route_steps"
    __table_args__ = (UniqueConstraint("route_code", "step_order", name="uq_repair_route_step_order"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_code: Mapped[str] = mapped_column(ForeignKey("repair_routes.code", ondelete="CASCADE"), index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    process_code: Mapped[str] = mapped_column(ForeignKey("wip_processes.code", ondelete="RESTRICT"))


class ProductLot(Base):
    __tablename__ = "product_lots"
    __table_args__ = (
        UniqueConstraint(
            "product_code",
            "lot_number",
            "storage_location_code",
            "unit",
            name="uq_product_lot_location_unit",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    storage_location_code: Mapped[str] = mapped_column(
        ForeignKey("storage_locations.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="gram")
    initial_quantity_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    current_quantity_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WarehouseMaterialTransfer(Base):
    __tablename__ = "warehouse_material_transfers"

    transfer_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    plant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    source_lot_id: Mapped[int] = mapped_column(
        ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sales_order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    source_storage_code: Mapped[str] = mapped_column(
        ForeignKey("warehouse_storages.code", ondelete="RESTRICT"), nullable=False
    )
    source_storage_name: Mapped[str] = mapped_column(String(150), nullable=False)
    source_location_code: Mapped[str] = mapped_column(
        ForeignKey("storage_locations.code", ondelete="RESTRICT"), nullable=False
    )
    source_location_name: Mapped[str] = mapped_column(String(150), nullable=False)
    destination_type: Mapped[WarehouseDestinationType] = mapped_column(
        Enum(WarehouseDestinationType, name="warehouse_destination_type_enum"), nullable=False, index=True
    )
    destination_process_code: Mapped[str | None] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    destination_process_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    destination_storage_code: Mapped[str | None] = mapped_column(
        ForeignKey("warehouse_storages.code", ondelete="RESTRICT"), nullable=True
    )
    destination_storage_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    destination_location_code: Mapped[str | None] = mapped_column(
        ForeignKey("storage_locations.code", ondelete="RESTRICT"), nullable=True
    )
    destination_location_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    destination_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=True
    )
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[WarehouseTransferStatus] = mapped_column(
        Enum(WarehouseTransferStatus, name="warehouse_transfer_status_enum"), nullable=False, index=True
    )
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    performed_by_name: Mapped[str] = mapped_column(String(201), nullable=False)
    reversed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WipLotJob(Base):
    __tablename__ = "wip_lot_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_transfer_number: Mapped[str] = mapped_column(
        ForeignKey("warehouse_material_transfers.transfer_number", ondelete="RESTRICT"), nullable=False, index=True
    )
    sales_order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    parent_job_id: Mapped[int | None] = mapped_column(ForeignKey("wip_lot_jobs.id", ondelete="RESTRICT"), nullable=True)
    production_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("production_executions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    repair_route_code: Mapped[str | None] = mapped_column(
        ForeignKey("repair_routes.code", ondelete="RESTRICT"), nullable=True
    )
    repair_step_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repair_return_process_code: Mapped[str | None] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=True
    )
    process_code: Mapped[str] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lot_segment_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    input_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    status: Mapped[WipLotStatus] = mapped_column(
        Enum(WipLotStatus, name="wip_lot_status_enum"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProductionExecution(Base):
    __tablename__ = "production_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_number: Mapped[str] = mapped_column(String(22), unique=True, nullable=False, index=True)
    process_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycle_time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    observed_cycle_time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("wip_lot_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="RESTRICT"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lot_segment_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    before_process_code: Mapped[str] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=False
    )
    before_process_name: Mapped[str] = mapped_column(String(150), nullable=False)
    after_process_code: Mapped[str | None] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=True
    )
    after_process_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    machine_code: Mapped[str | None] = mapped_column(ForeignKey("machines.code", ondelete="RESTRICT"), nullable=True)
    machine_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    processing_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    repair_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    ng_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    output_product_code: Mapped[str | None] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=True
    )
    output_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    repair_process_code: Mapped[str | None] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=True
    )
    repair_route_code: Mapped[str | None] = mapped_column(
        ForeignKey("repair_routes.code", ondelete="RESTRICT"), nullable=True
    )
    ng_limit_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ng_override_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ng_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ng_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    performed_by_name: Mapped[str] = mapped_column(String(201), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyProductionSequence(Base):
    __tablename__ = "daily_production_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyQualitySequence(Base):
    __tablename__ = "daily_quality_sequences"

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyFinishGoodSequence(Base):
    __tablename__ = "daily_finish_good_sequences"
    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyDeliverySequence(Base):
    __tablename__ = "daily_delivery_sequences"
    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class BillOfMaterialItem(Base):
    __tablename__ = "bill_of_material_items"
    __table_args__ = (
        UniqueConstraint("finished_product_code", "material_product_code", name="uq_bom_finished_material"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finished_product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="CASCADE"), nullable=False, index=True
    )
    material_product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinishGoodReceipt(Base):
    __tablename__ = "finish_good_receipts"
    receipt_number: Mapped[str] = mapped_column(String(22), primary_key=True)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_wip_job_id: Mapped[int] = mapped_column(
        ForeignKey("wip_lot_jobs.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lot_segment_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    storage_location_code: Mapped[str] = mapped_column(
        ForeignKey("storage_locations.code", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int] = mapped_column(ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[FinishGoodStatus] = mapped_column(
        Enum(FinishGoodStatus, name="finish_good_status_enum"), nullable=False, default=FinishGoodStatus.posted
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reversed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Delivery(Base):
    __tablename__ = "deliveries"
    delivery_number: Mapped[str] = mapped_column(String(22), primary_key=True)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sales_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sales_order_number: Mapped[str] = mapped_column(
        ForeignKey("sales_orders.sales_order_number", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    lot_id: Mapped[int] = mapped_column(ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transportation_code: Mapped[str | None] = mapped_column(
        ForeignKey("transportations.code", ondelete="RESTRICT"), nullable=True
    )
    driver_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status_enum"), nullable=False, default=DeliveryStatus.posted
    )
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    delivered_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeliveryLine(Base):
    """Line items for a delivery document; legacy Delivery rows remain readable."""

    __tablename__ = "delivery_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_number: Mapped[str] = mapped_column(
        ForeignKey("deliveries.delivery_number", ondelete="CASCADE"), nullable=False, index=True
    )
    sales_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lot_id: Mapped[int] = mapped_column(ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="RESTRICT"), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)


class QualityInspection(Base):
    __tablename__ = "quality_inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quality_number: Mapped[str] = mapped_column(String(22), unique=True, nullable=False, index=True)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift: Mapped[str] = mapped_column(String(20), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("wip_lot_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="RESTRICT"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lot_segment_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    before_process_code: Mapped[str] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=False
    )
    before_process_name: Mapped[str] = mapped_column(String(150), nullable=False)
    inspection_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    pass_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    repair_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    ng_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    repair_process_code: Mapped[str | None] = mapped_column(
        ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=True
    )
    repair_route_code: Mapped[str | None] = mapped_column(
        ForeignKey("repair_routes.code", ondelete="RESTRICT"), nullable=True
    )
    ng_limit_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ng_override_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ng_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ng_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    performed_by_name: Mapped[str] = mapped_column(String(201), nullable=False)
    reversed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Receiving(Base):
    __tablename__ = "receivings"

    receipt_number: Mapped[str] = mapped_column(String(21), primary_key=True)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lot_id: Mapped[int] = mapped_column(ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="gram")
    plant_code: Mapped[str] = mapped_column(ForeignKey("plants.code", ondelete="RESTRICT"), nullable=False, index=True)
    plant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_location_code: Mapped[str] = mapped_column(
        ForeignKey("storage_locations.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    storage_location_name: Mapped[str] = mapped_column(String(150), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[ReceivingSourceType | None] = mapped_column(
        Enum(ReceivingSourceType, name="receiving_source_type_enum"), nullable=True, index=True
    )
    source_code: Mapped[str | None] = mapped_column(
        ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    purchase_order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_order_items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sales_order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    material_allocation_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_order_material_allocations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    po_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transport_source: Mapped[str] = mapped_column(String(20), nullable=False, default="external")
    transportation_code: Mapped[str | None] = mapped_column(
        ForeignKey("transportations.code", ondelete="RESTRICT"), nullable=True, index=True
    )
    driver_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    receiver_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(201), nullable=False)
    status: Mapped[ReceivingStatus] = mapped_column(
        Enum(ReceivingStatus, name="receiving_status_enum"), nullable=False, default=ReceivingStatus.posted, index=True
    )
    reversed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    movement_type: Mapped[InventoryMovementType] = mapped_column(
        Enum(InventoryMovementType, name="inventory_movement_type_enum"), nullable=False, index=True
    )
    product_code: Mapped[str] = mapped_column(
        ForeignKey("products.code", ondelete="RESTRICT"), nullable=False, index=True
    )
    lot_id: Mapped[int] = mapped_column(ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="gram")
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    product_stock_after_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    lot_stock_after_grams: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ConsumableDisposition(Base):
    __tablename__ = "consumable_dispositions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_execution_id: Mapped[int] = mapped_column(
        ForeignKey("production_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_lot_id: Mapped[int] = mapped_column(
        ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    consumed_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    waste_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    scrap_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    scrap_storage_location_code: Mapped[str | None] = mapped_column(
        ForeignKey("storage_locations.code", ondelete="RESTRICT"), nullable=True
    )
    performed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
