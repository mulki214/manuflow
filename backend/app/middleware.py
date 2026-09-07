import jwt
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.database import SessionLocal
from app.models import Department, User
from app.module_permissions import resolve_department_access, resolve_department_membership
from app.security import decode_access_token


def is_purchasing_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/purchasing"
    return path == prefix or path.startswith(f"{prefix}/")


def is_sales_order_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/sales-orders"
    return path == prefix or path.startswith(f"{prefix}/")


def is_receiving_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/receiving"
    return path == prefix or path.startswith(f"{prefix}/")


def is_warehouse_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/warehouse"
    return path == prefix or path.startswith(f"{prefix}/")


def is_production_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/production"
    return path == prefix or path.startswith(f"{prefix}/")


def is_quality_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/quality"
    return path == prefix or path.startswith(f"{prefix}/")


def is_finish_good_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/finish-goods"
    return path == prefix or path.startswith(f"{prefix}/")


def is_delivery_path(path: str) -> bool:
    prefix = f"{settings.api_prefix}/delivery"
    return path == prefix or path.startswith(f"{prefix}/")


class DepartmentModuleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        protected_module: tuple[str, str, bool] | None = None
        if is_purchasing_path(request.url.path):
            protected_module = (settings.purchasing_department_code, "Purchasing", False)
        elif is_sales_order_path(request.url.path):
            protected_module = (settings.sales_department_code, "Sales", False)
        elif (
            is_receiving_path(request.url.path)
            or is_warehouse_path(request.url.path)
            or is_finish_good_path(request.url.path)
        ):
            protected_module = (settings.warehouse_department_code, "Warehouse", True)
        elif is_production_path(request.url.path):
            protected_module = (settings.production_department_code, "Production", True)
        elif is_quality_path(request.url.path):
            protected_module = (settings.quality_department_code, "Quality", True)
        elif is_delivery_path(request.url.path):
            # Delivery is role-based rather than department-based; the tuple
            # only marks the route as protected before the dedicated check.
            protected_module = ("", "Courier", True)
        if request.method == "OPTIONS" or protected_module is None:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Sesi tidak valid atau telah berakhir"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user_id = decode_access_token(token)
        except jwt.InvalidTokenError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Sesi tidak valid atau telah berakhir"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            if is_delivery_path(request.url.path):
                if not user or (user.role.strip().lower() != "courier" and user.access_level.value != "administrator"):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Only Courier users can access this module"},
                    )
                return await call_next(request)
            department_code, department_name, allow_members = protected_module
            department = await db.get(Department, department_code)
            resolver = resolve_department_membership if allow_members else resolve_department_access
            access = resolver(user, department) if user else None
            if access is None or not access.can_access:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": (
                            f"Only active {department_name} department members can access this module"
                            if allow_members
                            else f"Only the {department_name} PIC or Head can access this module"
                        )
                    },
                )
            request.state.department_module_access = access
            request.state.department_module_user_id = user.id

        return await call_next(request)


PurchasingDepartmentMiddleware = DepartmentModuleMiddleware
