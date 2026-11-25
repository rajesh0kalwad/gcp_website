import logging
import os
import re
from enum import Enum
from pathlib import Path
from typing import Annotated

import oracledb
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ServiceSlug(str, Enum):
    PREMIUM_WATCHES = "premium-watches"
    TRANSPORT = "transport"
    CONSULTATION = "consultation"


class InquiryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=2, max_length=120)]
    email: Annotated[str, Field(min_length=3, max_length=254)]
    service_slug: ServiceSlug
    message: Annotated[str, Field(min_length=10, max_length=4000)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value


class InquiryResponse(BaseModel):
    inquiry_id: int
    message: str


def connect_to_oracle() -> oracledb.Connection:
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")
    missing = [
        key
        for key, value in (
            ("ORACLE_USER", user),
            ("ORACLE_PASSWORD", password),
            ("ORACLE_DSN", dsn),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Oracle configuration: {', '.join(missing)}")
    return oracledb.connect(user=user, password=password, dsn=dsn)


app = FastAPI(
    title="Kalawad Enterprise API",
    description="Service information and customer enquiry endpoints.",
    version="1.0.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/services")
def list_services() -> list[dict[str, str]]:
    try:
        with connect_to_oracle() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT slug, title, description
                    FROM enterprise_services
                    WHERE is_active = 1
                    ORDER BY display_order
                    """
                )
                rows = cursor.fetchall()
        return [
            {"slug": slug, "title": title, "description": description}
            for slug, title, description in rows
        ]
    except (oracledb.Error, RuntimeError):
        logger.exception("Could not retrieve service information from Oracle")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service information is temporarily unavailable.",
        ) from None


@app.post(
    "/api/inquiries",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inquiry(inquiry: InquiryRequest) -> InquiryResponse:
    try:
        with connect_to_oracle() as connection:
            with connection.cursor() as cursor:
                inquiry_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                cursor.execute(
                    """
                    INSERT INTO enterprise_inquiries
                        (name, email, service_slug, message)
                    VALUES (:name, :email, :service_slug, :message)
                    RETURNING inquiry_id INTO :inquiry_id
                    """,
                    name=inquiry.name,
                    email=inquiry.email,
                    service_slug=inquiry.service_slug.value,
                    message=inquiry.message,
                    inquiry_id=inquiry_id,
                )
                connection.commit()
                created_id = inquiry_id.getvalue()
        return InquiryResponse(
            inquiry_id=int(created_id),
            message="Thank you. Your enquiry has been received.",
        )
    except (oracledb.Error, RuntimeError):
        logger.exception("Could not save an enquiry to Oracle")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not submit your enquiry right now. Please try again later.",
        ) from None


@app.get("/", include_in_schema=False)
def homepage() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
