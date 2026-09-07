from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import (
    AccessLevel,
    FulfillmentStatus,
    Gender,
    InventoryMovementType,
    ProductCategory,
    ProductSupplySource,
    PurchaseOrderStatus,
    ReceivingSourceType,
    ReceivingStatus,
    ReceivingTransportSource,
    SalesOrderStatus,
    SalesOrderType,
    StorageType,
    UnitOfMeasure,
    WarehouseDestinationType,
    WarehouseTransferStatus,
    WipLotStatus,
    WipProcessType,
    WorkflowStatus,
)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    gender: Gender
    role: str = Field(min_length=1, max_length=100)
    department_code: str | None = Field(default=None, max_length=15)
    access_level: AccessLevel = AccessLevel.staff
    ktp_number: str = Field(pattern=r"^\d{16}$")

    @field_validator("first_name", "last_name", "role")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class UserCreate(UserBase):
    department_code: str = Field(max_length=15)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    gender: Gender | None = None
    role: str | None = Field(default=None, min_length=1, max_length=100)
    department_code: str | None = Field(default=None, max_length=15)
    access_level: AccessLevel | None = None
    ktp_number: str | None = Field(default=None, pattern=r"^\d{16}$")
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    department_name: str | None = None
    pic_user_id: str | None = None
    pic_name: str | None = None
    pic_user_ids: list[str] = []
    pic_names: list[str] = []
    head_user_id: str | None = None
    head_name: str | None = None
    can_edit: bool = False
    can_delete: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_must_differ(self) -> "PasswordChangeRequest":
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password")
        return self


class TimestampedResponse(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowResponse(BaseModel):
    department_code: str | None = None
    created_by: str | None = None
    workflow_status: WorkflowStatus = WorkflowStatus.submitted
    can_edit: bool = False
    can_delete: bool = False


class DepartmentBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class DepartmentCreate(DepartmentBase):
    pic_user_ids: list[str] = Field(min_length=1)
    head_user_id: str = Field(max_length=9)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    pic_user_ids: list[str] | None = Field(default=None, min_length=1)
    head_user_id: str | None = Field(default=None, max_length=9)


class DepartmentResponse(DepartmentBase, TimestampedResponse, WorkflowResponse):
    code: str
    pic_user_id: str | None = None
    head_user_id: str | None = None
    pic_name: str | None = None
    pic_user_ids: list[str] = []
    pic_names: list[str] = []
    head_name: str | None = None


class PaginatedDepartments(BaseModel):
    items: list[DepartmentResponse]
    total: int
    page: int
    size: int


class CorporationBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=2000)
    phone_number: str = Field(min_length=3, max_length=32)
    contact_person_name: str = Field(min_length=1, max_length=150)
    contact_person_phone: str = Field(min_length=3, max_length=32)
    npwp: str = Field(min_length=5, max_length=32)
    is_customer: bool = False
    is_supplier: bool = False

    @model_validator(mode="after")
    def require_business_type(self) -> "CorporationBase":
        if not self.is_customer and not self.is_supplier:
            raise ValueError("Corporation must be a customer, supplier, or both")
        return self


class CorporationCreate(CorporationBase):
    pass


class CorporationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=2000)
    phone_number: str | None = Field(default=None, min_length=3, max_length=32)
    contact_person_name: str | None = Field(default=None, min_length=1, max_length=150)
    contact_person_phone: str | None = Field(default=None, min_length=3, max_length=32)
    npwp: str | None = Field(default=None, min_length=5, max_length=32)
    is_customer: bool | None = None
    is_supplier: bool | None = None


class CorporationResponse(CorporationBase, TimestampedResponse, WorkflowResponse):
    code: str


class PlantBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    full_address: str = Field(min_length=1, max_length=2000)


class PlantCreate(PlantBase):
    pass


class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    full_address: str | None = Field(default=None, min_length=1, max_length=2000)


class PlantResponse(PlantBase, TimestampedResponse, WorkflowResponse):
    code: str


class ProductBase(BaseModel):
    customer_code: str = Field(min_length=1, max_length=15)
    supplier_code: str | None = Field(default=None, min_length=1, max_length=15)
    supply_source: ProductSupplySource = ProductSupplySource.external_supplier
    part_name: str = Field(min_length=1, max_length=200)
    part_no: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    gross_weight: Decimal = Field(ge=0, decimal_places=3)
    nett_weight: Decimal = Field(ge=0, decimal_places=3)
    category: ProductCategory = ProductCategory.finished_good

    @model_validator(mode="after")
    def fill_default_description(self) -> "ProductBase":
        if not self.description or not self.description.strip():
            self.description = f"{self.part_name} {self.part_no}"
        if self.supply_source == ProductSupplySource.external_supplier and not self.supplier_code:
            raise ValueError("Supplier is required for products supplied externally")
        if self.supply_source == ProductSupplySource.manufactured_internally:
            self.supplier_code = None
        return self


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    customer_code: str | None = Field(default=None, min_length=1, max_length=15)
    supplier_code: str | None = Field(default=None, min_length=1, max_length=15)
    supply_source: ProductSupplySource | None = None
    part_name: str | None = Field(default=None, min_length=1, max_length=200)
    part_no: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    gross_weight: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    nett_weight: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    category: ProductCategory | None = None


class ProductResponse(ProductBase, TimestampedResponse, WorkflowResponse):
    code: str
    customer_name: str
    supplier_name: str
    current_stock_grams: Decimal
    stock_by_unit: dict[str, Decimal] = {}


class ProductQrResolveResponse(BaseModel):
    product_code: str
    product_name: str
    description: str
    lot_id: int | None = None
    lot_number: str | None = None
    unit: str | None = None
    available_quantity: Decimal | None = None


class BomItemInput(BaseModel):
    material_product_code: str = Field(min_length=1, max_length=15)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    unit: UnitOfMeasure


class BillOfMaterialItemResponse(BomItemInput):
    id: int
    material_description: str
    is_active: bool


class BillOfMaterialReplace(BaseModel):
    items: list[BomItemInput] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_materials(self) -> "BillOfMaterialReplace":
        if len({item.material_product_code for item in self.items}) != len(self.items):
            raise ValueError("The same material cannot be included more than once")
        return self


class BillOfMaterialResponse(BaseModel):
    finished_product_code: str
    items: list[BillOfMaterialItemResponse]


class MachineBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    specification: str = Field(min_length=1, max_length=2000)
    machine_type: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1800, le=2200)
    country_of_origin: str = Field(min_length=1, max_length=100)
    plant_code: str = Field(min_length=5, max_length=5)


class MachineCreate(MachineBase):
    pass


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    specification: str | None = Field(default=None, min_length=1, max_length=2000)
    machine_type: str | None = Field(default=None, min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1800, le=2200)
    country_of_origin: str | None = Field(default=None, min_length=1, max_length=100)
    plant_code: str | None = Field(default=None, min_length=5, max_length=5)


class MachineResponse(MachineBase, TimestampedResponse, WorkflowResponse):
    code: str
    plant_name: str


class PaginatedCorporations(BaseModel):
    items: list[CorporationResponse]
    total: int
    page: int
    size: int


class PaginatedPlants(BaseModel):
    items: list[PlantResponse]
    total: int
    page: int
    size: int


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    size: int


class PaginatedMachines(BaseModel):
    items: list[MachineResponse]
    total: int
    page: int
    size: int


class ModuleAccessResponse(BaseModel):
    module: str = "purchasing"
    department_code: str
    can_access: bool
    is_pic: bool
    is_head: bool
    can_review: bool


class PurchaseOrderItemInput(BaseModel):
    product_code: str = Field(min_length=1, max_length=15)
    quantity_grams: Decimal = Field(gt=0, decimal_places=3)
    unit: UnitOfMeasure = UnitOfMeasure.pcs
    unit_price: Decimal = Field(ge=0, decimal_places=4)
    remark: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_discrete_quantity(self) -> "PurchaseOrderItemInput":
        from app.operational_services import require_whole_quantity

        require_whole_quantity(self.quantity_grams, self.unit.value)
        return self

    @field_validator("remark")
    @classmethod
    def strip_remark(cls, value: str) -> str:
        return value.strip()


class PurchaseOrderBase(BaseModel):
    po_date: date
    supplier_code: str = Field(min_length=1, max_length=15)
    quotation_reference: str | None = Field(default=None, max_length=100)
    quotation_date: date | None = None
    requested_delivery_date: date
    delivery_plant_code: str = Field(min_length=5, max_length=5)
    notes: str = Field(default="", max_length=5000)
    payment_terms_days: int = Field(default=30, ge=0, le=3650)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    ppn_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=3)
    pph23_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=3)
    items: list[PurchaseOrderItemInput] = Field(min_length=1, max_length=100)

    @field_validator("quotation_reference", mode="before")
    @classmethod
    def empty_quotation_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("quotation_reference", "notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def validate_purchase_order(self) -> "PurchaseOrderBase":
        if self.quotation_reference and self.quotation_date is None:
            raise ValueError("Quotation date is required when quotation reference is provided")
        if self.requested_delivery_date < self.po_date:
            raise ValueError("Requested delivery date cannot be before PO date")
        product_codes = [item.product_code for item in self.items]
        if len(set(product_codes)) != len(product_codes):
            raise ValueError("The same product cannot be added more than once")
        return self


class PurchaseOrderCreate(PurchaseOrderBase):
    pass


class PurchaseOrderUpdate(PurchaseOrderBase):
    pass


class PurchaseOrderItemResponse(BaseModel):
    id: int
    line_number: int
    product_code: str
    part_name: str
    part_no: str
    description: str
    quantity_grams: Decimal
    unit: str
    received_quantity: Decimal
    outstanding_quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    remark: str

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderResponse(BaseModel):
    po_number: str
    po_date: date
    supplier_code: str
    supplier_name: str
    supplier_address: str
    supplier_phone: str
    supplier_contact_person: str
    quotation_reference: str | None
    quotation_date: date | None
    requested_delivery_date: date
    delivery_plant_code: str
    delivery_plant_name: str
    delivery_address: str
    notes: str
    payment_terms_days: int
    payment_due_date: date
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    ppn_rate: Decimal
    ppn_amount: Decimal
    pph23_rate: Decimal
    pph23_amount: Decimal
    grand_total: Decimal
    status: PurchaseOrderStatus
    fulfillment_status: FulfillmentStatus
    department_code: str
    created_by: str
    created_by_name: str
    reviewed_by: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    can_edit: bool
    can_delete: bool
    can_review: bool
    creator_qr_payload: str
    approval_qr_payload: str | None
    items: list[PurchaseOrderItemResponse]
    created_at: datetime
    updated_at: datetime


class PaginatedPurchaseOrders(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
    page: int
    size: int


class PurchaseOrderRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        return value.strip()


class SalesOrderItemInput(BaseModel):
    product_code: str = Field(min_length=1, max_length=15)
    quantity_grams: Decimal = Field(gt=0, decimal_places=3)
    unit: UnitOfMeasure = UnitOfMeasure.pcs
    unit_price: Decimal = Field(ge=0, decimal_places=4)
    remark: str = Field(default="", max_length=2000)
    outstanding_note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_discrete_quantity(self) -> "SalesOrderItemInput":
        from app.operational_services import require_whole_quantity

        require_whole_quantity(self.quantity_grams, self.unit.value)
        return self

    @field_validator("remark", "outstanding_note")
    @classmethod
    def strip_sales_item_remark(cls, value: str) -> str:
        return value.strip()


class SalesOrderBase(BaseModel):
    po_receipt_date: date
    customer_po_date: date
    customer_po_number: str = Field(min_length=1, max_length=100)
    customer_code: str = Field(min_length=1, max_length=15)
    ship_to_name: str | None = Field(default=None, max_length=200)
    ship_to_address: str | None = Field(default=None, max_length=2000)
    ship_to_contact_person: str | None = Field(default=None, max_length=150)
    ship_to_phone: str | None = Field(default=None, max_length=32)
    delivery_date: date
    order_type: SalesOrderType = SalesOrderType.mass_pro
    notes: str = Field(default="", max_length=5000)
    items: list[SalesOrderItemInput] = Field(min_length=1, max_length=100)

    @field_validator("order_type", mode="before")
    @classmethod
    def migrate_legacy_order_type(cls, value: object) -> object:
        return {
            "regular": "mass_pro",
            "sample": "job_order",
            "replacement": "job_order",
        }.get(value, value)

    @field_validator(
        "customer_po_number",
        "ship_to_name",
        "ship_to_address",
        "ship_to_contact_person",
        "ship_to_phone",
        "notes",
    )
    @classmethod
    def strip_sales_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def validate_sales_order(self) -> "SalesOrderBase":
        if self.po_receipt_date < self.customer_po_date:
            raise ValueError("PO receipt date cannot be before customer PO date")
        if self.delivery_date < self.po_receipt_date:
            raise ValueError("Delivery date cannot be before PO receipt date")
        product_codes = [item.product_code for item in self.items]
        if len(set(product_codes)) != len(product_codes):
            raise ValueError("The same product cannot be added more than once")
        return self


class SalesOrderCreate(SalesOrderBase):
    pass


class SalesOrderUpdate(SalesOrderBase):
    pass


class SalesOrderItemResponse(BaseModel):
    id: int
    line_number: int
    product_code: str
    part_name: str
    part_no: str
    description: str
    quantity_grams: Decimal
    unit: str
    material_received_quantity: Decimal
    outstanding_material_quantity: Decimal
    delivered_quantity: Decimal
    outstanding_order_quantity: Decimal
    outstanding_note: str
    unit_price: Decimal
    amount: Decimal
    remark: str
    wip_quantity: Decimal = Decimal("0")
    finish_good_quantity: Decimal = Decimal("0")
    dispatched_quantity: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class SalesOrderResponse(BaseModel):
    sales_order_number: str
    po_receipt_date: date
    customer_po_date: date
    customer_po_number: str
    customer_code: str
    customer_name: str
    bill_to_address: str
    bill_to_phone: str
    ship_to_name: str
    ship_to_address: str
    ship_to_contact_person: str
    ship_to_phone: str
    delivery_date: date
    order_type: SalesOrderType
    notes: str
    currency: str
    subtotal: Decimal
    grand_total: Decimal
    status: SalesOrderStatus
    fulfillment_status: FulfillmentStatus
    department_code: str
    created_by: str
    created_by_name: str
    reviewed_by: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    can_edit: bool
    can_delete: bool
    can_review: bool
    creator_qr_payload: str
    approval_qr_payload: str | None
    items: list[SalesOrderItemResponse]
    created_at: datetime
    updated_at: datetime


class PaginatedSalesOrders(BaseModel):
    items: list[SalesOrderResponse]
    total: int
    page: int
    size: int
    total_order: int = 0
    outstanding_order: int = 0
    total_material_by_unit: dict[str, Decimal] = {}
    outstanding_material_by_unit: dict[str, Decimal] = {}


class SalesOrderRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_sales_rejection_reason(cls, value: str) -> str:
        return value.strip()


class StorageLocationBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    plant_code: str = Field(min_length=5, max_length=5)
    storage_code: str = Field(min_length=1, max_length=15)
    description: str = Field(default="", max_length=2000)


class StorageLocationCreate(StorageLocationBase):
    pass


class StorageLocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    plant_code: str | None = Field(default=None, min_length=5, max_length=5)
    storage_code: str | None = Field(default=None, min_length=1, max_length=15)
    description: str | None = Field(default=None, max_length=2000)


class StorageLocationResponse(StorageLocationBase, TimestampedResponse, WorkflowResponse):
    code: str
    plant_name: str
    storage_name: str
    storage_type: StorageType


class PaginatedStorageLocations(BaseModel):
    items: list[StorageLocationResponse]
    total: int
    page: int
    size: int


class WarehouseStorageBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    storage_type: StorageType
    plant_code: str = Field(min_length=5, max_length=5)
    description: str = Field(default="", max_length=2000)


class WarehouseStorageCreate(WarehouseStorageBase):
    pass


class WarehouseStorageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    storage_type: StorageType | None = None
    plant_code: str | None = Field(default=None, min_length=5, max_length=5)
    description: str | None = Field(default=None, max_length=2000)


class WarehouseStorageResponse(WarehouseStorageBase, TimestampedResponse, WorkflowResponse):
    code: str
    plant_name: str


class PaginatedWarehouseStorages(BaseModel):
    items: list[WarehouseStorageResponse]
    total: int
    page: int
    size: int


class TransportationBase(BaseModel):
    vehicle_number: str = Field(min_length=1, max_length=50)
    vehicle_type: str = Field(min_length=1, max_length=100)
    brand_name: str | None = Field(default=None, max_length=100)
    manufacturing_year: int | None = Field(default=None, ge=1900, le=2200)
    carrier_name: str = Field(min_length=1, max_length=200)
    capacity: Decimal | None = Field(default=None, gt=0, decimal_places=3)
    notes: str = Field(default="", max_length=2000)
    is_active: bool = True


class TransportationCreate(TransportationBase):
    pass


class TransportationUpdate(BaseModel):
    vehicle_number: str | None = Field(default=None, min_length=1, max_length=50)
    vehicle_type: str | None = Field(default=None, min_length=1, max_length=100)
    brand_name: str | None = Field(default=None, max_length=100)
    manufacturing_year: int | None = Field(default=None, ge=1900, le=2200)
    carrier_name: str | None = Field(default=None, min_length=1, max_length=200)
    capacity: Decimal | None = Field(default=None, gt=0, decimal_places=3)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class TransportationResponse(TransportationBase, TimestampedResponse, WorkflowResponse):
    code: str


class PaginatedTransportations(BaseModel):
    items: list[TransportationResponse]
    total: int
    page: int
    size: int


class ReceivingCreate(BaseModel):
    receipt_date: date
    source_type: ReceivingSourceType
    source_code: str = Field(min_length=1, max_length=15)
    source_document_item_id: int
    # Explicit UI context. The legacy source fields remain stored for existing receipts.
    document_type: str | None = Field(default=None, pattern="^(purchase_order|sales_order)$")
    customer_code: str | None = Field(default=None, min_length=1, max_length=15)
    lot_number: str = Field(min_length=1, max_length=100)
    quantity_grams: Decimal = Field(gt=0, decimal_places=3)
    plant_code: str = Field(min_length=5, max_length=5)
    storage_location_code: str = Field(min_length=1, max_length=15)
    document_number: str | None = Field(default=None, max_length=100)
    transport_source: ReceivingTransportSource = ReceivingTransportSource.external
    transportation_code: str | None = Field(default=None, max_length=15)
    vehicle_number: str | None = Field(default=None, max_length=50)
    driver_name: str | None = Field(default=None, max_length=150)
    notes: str = Field(default="", max_length=5000)

    @field_validator(
        "lot_number",
        "document_number",
        "vehicle_number",
        "driver_name",
        "notes",
    )
    @classmethod
    def strip_receiving_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def validate_transport_source(self) -> "ReceivingCreate":
        if self.document_type == "purchase_order" and self.source_type != ReceivingSourceType.customer:
            raise ValueError("Purchase Order Receiving must use the supplier source")
        if self.document_type == "sales_order" and self.source_type != ReceivingSourceType.supplier:
            raise ValueError("Sales Order Receiving must use the supplier source")
        if self.transport_source == ReceivingTransportSource.internal and not self.transportation_code:
            raise ValueError("An internal transportation record is required for Internal transport")
        if self.transport_source == ReceivingTransportSource.internal and (self.vehicle_number or self.driver_name):
            raise ValueError("Vehicle Number and Driver Name are derived from Internal transport")
        if self.transport_source == ReceivingTransportSource.external and self.transportation_code:
            raise ValueError("Transportation record can only be selected for Internal transport")
        return self


class ReceivingSourceItemResponse(BaseModel):
    source_type: ReceivingSourceType
    source_code: str
    source_name: str
    document_number: str
    item_id: int
    product_code: str
    product_description: str
    ordered_quantity: Decimal
    received_quantity: Decimal
    outstanding_quantity: Decimal
    unit: str


class ReceivingSourceItemsResponse(BaseModel):
    items: list[ReceivingSourceItemResponse]


class ReceivingReversal(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_reversal_reason(cls, value: str) -> str:
        return value.strip()


class ReceivingResponse(BaseModel):
    receipt_number: str
    receipt_date: date
    product_code: str
    product_name: str
    description: str
    lot_number: str
    quantity_grams: Decimal
    unit: str
    plant_code: str
    plant_name: str
    storage_location_code: str
    storage_location_name: str
    source: str
    source_type: ReceivingSourceType | None
    source_code: str | None
    source_document_item_id: int | None
    document_number: str | None
    po_number: str | None
    vehicle_number: str | None
    transport_source: ReceivingTransportSource
    driver_name: str | None
    transportation_code: str | None
    notes: str
    receiver_id: str
    receiver_name: str
    status: ReceivingStatus
    reversed_by: str | None
    reversed_by_name: str | None
    reversed_at: datetime | None
    reversal_reason: str | None
    product_stock_after_grams: Decimal
    lot_stock_after_grams: Decimal
    can_reverse: bool
    created_at: datetime
    updated_at: datetime


class PaginatedReceivings(BaseModel):
    items: list[ReceivingResponse]
    total: int
    page: int
    size: int


class ProductLotResponse(BaseModel):
    id: int
    product_code: str
    lot_number: str
    plant_code: str
    storage_location_code: str
    unit: str
    initial_quantity_grams: Decimal
    current_quantity_grams: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductStockResponse(BaseModel):
    product_code: str
    product_name: str
    current_stock_grams: Decimal
    lot_total_grams: Decimal
    lots: list[ProductLotResponse]
    stock_by_unit: dict[str, Decimal] = {}


class InventoryMovementResponse(BaseModel):
    id: int
    movement_date: datetime
    movement_type: InventoryMovementType
    product_code: str
    lot_id: int
    unit: str
    quantity_grams: Decimal
    product_stock_after_grams: Decimal
    lot_stock_after_grams: Decimal
    reference_type: str
    reference_number: str
    performed_by: str
    notes: str

    model_config = ConfigDict(from_attributes=True)


class PaginatedInventoryMovements(BaseModel):
    items: list[InventoryMovementResponse]
    total: int
    page: int
    size: int


class WipProcessCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=2000)
    process_type: WipProcessType = WipProcessType.production
    plant_code: str = Field(min_length=5, max_length=5)
    is_active: bool = True

    @field_validator("code", "name", "description")
    @classmethod
    def normalize_process_text(cls, value: str) -> str:
        return value.strip()


class WipProcessUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    process_type: WipProcessType | None = None
    plant_code: str | None = Field(default=None, min_length=5, max_length=5)
    is_active: bool | None = None


class WipProcessResponse(BaseModel):
    code: str
    name: str
    description: str
    process_type: WipProcessType
    plant_code: str
    plant_name: str
    is_active: bool
    can_edit: bool
    can_delete: bool
    created_at: datetime
    updated_at: datetime


class PaginatedWipProcesses(BaseModel):
    items: list[WipProcessResponse]
    total: int
    page: int
    size: int


class ProductionWipJobResponse(BaseModel):
    id: int
    source_transfer_number: str
    parent_job_id: int | None
    production_execution_id: int | None
    repair_route_code: str | None
    repair_step_order: int | None
    repair_return_process_code: str | None
    process_code: str
    process_name: str
    process_type: WipProcessType
    product_code: str
    product_name: str
    description: str
    lot_number: str
    lot_segment_code: str
    plant_code: str
    plant_name: str
    unit: str
    input_quantity: Decimal
    current_quantity: Decimal
    status: WipLotStatus
    can_complete: bool
    created_at: datetime
    updated_at: datetime


class PaginatedProductionWipJobs(BaseModel):
    items: list[ProductionWipJobResponse]
    total: int
    page: int
    size: int


class ProductProcessStandardCreate(BaseModel):
    product_code: str = Field(max_length=15)
    process_code: str = Field(max_length=20)
    machine_code: str | None = Field(default=None, max_length=15)
    working_hours: Decimal = Field(gt=0, decimal_places=3)
    expected_output_quantity: Decimal = Field(gt=0, decimal_places=3)
    output_unit: UnitOfMeasure
    target_cycle_time_seconds: Decimal | None = Field(default=None, gt=0, decimal_places=3)
    maximum_ng_quantity: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    maximum_ng_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=4)
    is_active: bool = True


class ConsumableDispositionCreate(BaseModel):
    source_lot_id: int
    consumed_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    waste_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    scrap_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    scrap_storage_location_code: str | None = Field(default=None, max_length=15)

    @model_validator(mode="after")
    def validate_disposition(self) -> "ConsumableDispositionCreate":
        if self.consumed_quantity + self.waste_quantity + self.scrap_quantity <= 0:
            raise ValueError("At least one consumable disposition quantity is required")
        if self.scrap_quantity > 0 and not self.scrap_storage_location_code:
            raise ValueError("Scrap Storage Location is required when Scrap Quantity is entered")
        return self


class ConsumableDispositionResponse(ConsumableDispositionCreate):
    id: int
    production_execution_id: int
    unit: str
    performed_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductProcessStandardResponse(ProductProcessStandardCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RepairRouteCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=150)
    product_code: str = Field(max_length=15)
    source_process_code: str = Field(max_length=20)
    return_process_code: str | None = Field(default=None, max_length=20)
    step_process_codes: list[str] = Field(min_length=1)
    is_active: bool = True


class RepairRouteResponse(RepairRouteCreate):
    created_at: datetime
    updated_at: datetime


class ProductionExecutionCreate(BaseModel):
    process_date: date
    shift: str = Field(min_length=1, max_length=20)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    break_duration_minutes: int = Field(default=0, ge=0, le=1440)
    observed_cycle_time_seconds: Decimal | None = Field(default=None, gt=0, decimal_places=3)
    ng_override_reason: str | None = Field(default=None, max_length=2000)
    processing_quantity: Decimal = Field(gt=0, decimal_places=3)
    good_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    repair_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    ng_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    next_process_code: str | None = Field(default=None, max_length=20)
    repair_process_code: str | None = Field(default=None, max_length=20)
    repair_route_code: str | None = Field(default=None, max_length=20)
    output_product_code: str | None = Field(default=None, max_length=15)
    output_unit: str | None = Field(default=None, max_length=10)
    machine_code: str | None = Field(default=None, max_length=15)
    notes: str = Field(default="", max_length=5000)

    @field_validator(
        "shift",
        "next_process_code",
        "repair_process_code",
        "output_product_code",
        "output_unit",
        "machine_code",
        "notes",
    )
    @classmethod
    def normalize_execution_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def validate_outcomes(self) -> "ProductionExecutionCreate":
        outcome_total = self.good_quantity + self.repair_quantity + self.ng_quantity
        if outcome_total != self.processing_quantity:
            raise ValueError("Good, Repair, and NG Quantity must equal Processing Quantity")
        if self.repair_quantity > 0 and not (self.repair_process_code or self.repair_route_code):
            raise ValueError("Repair Quantity requires a Repair Process or Repair Route")
        if self.started_at and self.ended_at and self.ended_at <= self.started_at:
            raise ValueError("Production End Time must be after Start Time")
        return self


class ProductionExecutionReverse(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class ProductionExecutionResponse(BaseModel):
    id: int
    production_number: str
    process_date: date
    shift: str
    started_at: datetime | None
    ended_at: datetime | None
    break_duration_minutes: int
    cycle_time_seconds: Decimal | None
    observed_cycle_time_seconds: Decimal | None
    job_id: int
    product_code: str
    product_name: str
    description: str
    lot_number: str
    lot_segment_code: str
    plant_code: str
    plant_name: str
    unit: str
    before_process_code: str
    before_process_name: str
    after_process_code: str | None
    after_process_name: str | None
    machine_code: str | None
    machine_name: str | None
    processing_quantity: Decimal
    good_quantity: Decimal
    repair_quantity: Decimal
    ng_quantity: Decimal
    output_product_code: str | None
    output_unit: str | None
    repair_process_code: str | None
    repair_process_name: str | None
    repair_route_code: str | None
    ng_limit_exceeded: bool
    ng_override_by: str | None
    ng_override_at: datetime | None
    ng_override_reason: str | None
    notes: str
    performed_by: str
    performed_by_name: str
    reversed_by: str | None
    reversed_at: datetime | None
    reversal_reason: str | None
    can_reverse: bool
    good_segment_code: str | None
    repair_segment_code: str | None
    ng_segment_code: str | None
    created_at: datetime


class PaginatedProductionExecutions(BaseModel):
    items: list[ProductionExecutionResponse]
    total: int
    page: int
    size: int


class QualityInspectionCreate(BaseModel):
    inspection_date: date
    shift: str = Field(min_length=1, max_length=20)
    inspection_quantity: Decimal = Field(gt=0, decimal_places=3)
    pass_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    repair_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    ng_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    repair_process_code: str | None = Field(default=None, max_length=20)
    repair_route_code: str | None = Field(default=None, max_length=20)
    ng_override_reason: str | None = Field(default=None, max_length=2000)
    problem: str = Field(default="", max_length=5000)
    notes: str = Field(default="", max_length=5000)

    @field_validator("shift", "repair_process_code", "problem", "notes")
    @classmethod
    def normalize_quality_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def validate_outcomes(self) -> "QualityInspectionCreate":
        if self.pass_quantity + self.repair_quantity + self.ng_quantity != self.inspection_quantity:
            raise ValueError("Pass, Repair, and NG Quantity must equal Inspection Quantity")
        if self.repair_quantity > 0 and not (self.repair_process_code or self.repair_route_code):
            raise ValueError("Repair Quantity requires a Repair Process or Repair Route")
        return self


class QualityInspectionReverse(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class QualityWipJobResponse(ProductionWipJobResponse):
    can_inspect: bool


class PaginatedQualityWipJobs(BaseModel):
    items: list[QualityWipJobResponse]
    total: int
    page: int
    size: int


class QualityInspectionResponse(BaseModel):
    id: int
    quality_number: str
    inspection_date: date
    shift: str
    job_id: int
    product_code: str
    product_name: str
    description: str
    lot_number: str
    lot_segment_code: str
    plant_code: str
    plant_name: str
    unit: str
    before_process_code: str
    before_process_name: str
    inspection_quantity: Decimal
    pass_quantity: Decimal
    repair_quantity: Decimal
    ng_quantity: Decimal
    repair_process_code: str | None
    repair_process_name: str | None
    repair_route_code: str | None
    ng_limit_exceeded: bool
    ng_override_by: str | None
    ng_override_at: datetime | None
    ng_override_reason: str | None
    problem: str
    notes: str
    performed_by: str
    performed_by_name: str
    reversed_by: str | None
    reversed_at: datetime | None
    reversal_reason: str | None
    can_reverse: bool
    pass_segment_code: str | None
    repair_segment_code: str | None
    ng_segment_code: str | None
    created_at: datetime


class PaginatedQualityInspections(BaseModel):
    items: list[QualityInspectionResponse]
    total: int
    page: int
    size: int


class FinishGoodPostCreate(BaseModel):
    receipt_date: date
    storage_location_code: str = Field(min_length=1, max_length=15)
    notes: str = Field(default="", max_length=2000)


class FinishGoodReverse(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class FinishGoodResponse(BaseModel):
    receipt_number: str
    receipt_date: date
    product_code: str
    lot_number: str
    quantity: Decimal
    unit: str
    plant_code: str
    storage_location_code: str
    status: str
    can_reverse: bool
    created_at: datetime


class DeliveryCreate(BaseModel):
    delivery_date: date
    sales_order_item_id: int
    lot_id: int
    quantity: Decimal = Field(gt=0, decimal_places=3)
    transportation_code: str | None = Field(default=None, max_length=15)
    driver_name: str = Field(min_length=1, max_length=150)
    notes: str = Field(default="", max_length=2000)


class DeliveryLineCreate(BaseModel):
    sales_order_item_id: int
    lot_id: int
    quantity: Decimal = Field(gt=0, decimal_places=3)


class DeliveryBatchCreate(BaseModel):
    delivery_date: date
    transportation_code: str | None = Field(default=None, max_length=15)
    driver_name: str = Field(min_length=1, max_length=150)
    notes: str = Field(default="", max_length=2000)
    lines: list[DeliveryLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_lots(self) -> "DeliveryBatchCreate":
        pairs = [(line.sales_order_item_id, line.lot_id) for line in self.lines]
        if len(pairs) != len(set(pairs)):
            raise ValueError("A Sales Order item and Finished Goods lot can only appear once")
        return self


class DeliveryReverse(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class DeliveryConfirm(BaseModel):
    notes: str = Field(default="", max_length=2000)


class DeliveryLineResponse(BaseModel):
    sales_order_item_id: int
    product_code: str
    lot_id: int
    lot_number: str
    quantity: Decimal
    unit: str


class DeliveryResponse(BaseModel):
    delivery_number: str
    delivery_date: date
    sales_order_number: str
    customer_name: str
    product_code: str
    lot_number: str
    quantity: Decimal
    unit: str
    vehicle_number: str | None
    transportation_code: str | None
    driver_name: str | None
    notes: str
    status: str
    can_reverse: bool
    can_confirm_delivery: bool
    delivered_at: datetime | None
    created_at: datetime
    lines: list[DeliveryLineResponse] = Field(default_factory=list)


class PaginatedFinishGoods(BaseModel):
    items: list[FinishGoodResponse]
    total: int
    page: int
    size: int


class PaginatedDeliveries(BaseModel):
    items: list[DeliveryResponse]
    total: int
    page: int
    size: int


class WarehouseStockLotResponse(BaseModel):
    lot_id: int
    product_code: str
    product_name: str
    description: str
    lot_number: str
    quantity: Decimal
    unit: str
    plant_code: str
    plant_name: str
    storage_code: str
    storage_name: str
    storage_type: StorageType
    storage_location_code: str
    storage_location_name: str


class PaginatedWarehouseStockLots(BaseModel):
    items: list[WarehouseStockLotResponse]
    total: int
    page: int
    size: int


class WarehouseMaterialTransferCreate(BaseModel):
    transfer_date: date
    source_lot_id: int
    quantity: Decimal = Field(gt=0, decimal_places=3)
    destination_type: WarehouseDestinationType
    destination_process_code: str | None = Field(default=None, max_length=20)
    destination_location_code: str | None = Field(default=None, max_length=15)
    document_number: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_destination(self) -> "WarehouseMaterialTransferCreate":
        if self.destination_type == WarehouseDestinationType.wip:
            if not self.destination_process_code or self.destination_location_code:
                raise ValueError("WIP destination requires one Process and no Finished Goods Location")
        elif not self.destination_location_code or self.destination_process_code:
            raise ValueError("Finished Goods destination requires one Storage Location and no WIP Process")
        return self


class WarehouseTransferReversal(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class WarehouseMaterialTransferResponse(BaseModel):
    transfer_number: str
    transfer_date: date
    product_code: str
    product_name: str
    description: str
    lot_number: str
    quantity: Decimal
    unit: str
    plant_code: str
    plant_name: str
    source_lot_id: int
    source_storage_code: str
    source_storage_name: str
    source_location_code: str
    source_location_name: str
    destination_type: WarehouseDestinationType
    destination_process_code: str | None
    destination_process_name: str | None
    destination_storage_code: str | None
    destination_storage_name: str | None
    destination_location_code: str | None
    destination_location_name: str | None
    document_number: str | None
    notes: str
    status: WarehouseTransferStatus
    performed_by: str
    performed_by_name: str
    reversed_by: str | None
    reversed_by_name: str | None
    reversed_at: datetime | None
    reversal_reason: str | None
    wip_job_id: int | None
    wip_lot_segment_code: str | None
    wip_status: WipLotStatus | None
    can_reverse: bool
    created_at: datetime
    updated_at: datetime


class PaginatedWarehouseMaterialTransfers(BaseModel):
    items: list[WarehouseMaterialTransferResponse]
    total: int
    page: int
    size: int
