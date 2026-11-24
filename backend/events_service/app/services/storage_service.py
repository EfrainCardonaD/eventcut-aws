import os
import uuid
from urllib.parse import unquote

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import status

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.core.settings import settings

# Cargar variables .env locales si existen (en AWS se inyectan por entorno/Docker)
load_dotenv()

# Variables heredadas expuestas a nivel modulo para compatibilidad con tests existentes
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME") or os.getenv("R2_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
AWS_S3_PUBLIC_HOST = os.getenv("AWS_S3_PUBLIC_HOST") or os.getenv("S3_PUBLIC_HOST") or os.getenv("R2_PUBLIC_HOST")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or os.getenv("R2_ENDPOINT_URL")

# Aliases de compatibilidad hacia atrás
BUCKET_NAME = AWS_S3_BUCKET
R2_PUBLIC_HOST = AWS_S3_PUBLIC_HOST

_NAMESPACE_PREFIXES = {
    "events": "events/",
    "comunidad": "comunidad/",
}


def get_bucket_name() -> str | None:
    return (
        os.getenv("AWS_S3_BUCKET")
        or os.getenv("S3_BUCKET_NAME")
        or os.getenv("R2_BUCKET_NAME")
        or BUCKET_NAME
        or AWS_S3_BUCKET
    )


def get_aws_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or AWS_REGION or "us-east-1"


def get_public_host() -> str:
    explicit = (
        os.getenv("AWS_S3_PUBLIC_HOST")
        or os.getenv("S3_PUBLIC_HOST")
        or os.getenv("R2_PUBLIC_HOST")
        or AWS_S3_PUBLIC_HOST
        or R2_PUBLIC_HOST
    )
    if explicit:
        return explicit.strip().rstrip("/")

    bucket = get_bucket_name()
    if bucket:
        region = get_aws_region()
        return f"https://{bucket}.s3.{region}.amazonaws.com"
    return ""


def _get_namespace_prefix(namespace: str) -> str:
    try:
        return _NAMESPACE_PREFIXES[namespace]
    except KeyError as exc:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="El namespace de almacenamiento no está permitido.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"namespace": namespace, "allowed": sorted(_NAMESPACE_PREFIXES.keys())},
        ) from exc


def _get_pending_prefix(namespace: str) -> str:
    return f"{_get_namespace_prefix(namespace)}pending/"


def _get_s3_client():
    """
    Inicializa un cliente nativo de AWS S3 usando boto3.
    En AWS EC2 utiliza automáticamente el IAM Instance Profile (LabInstanceProfile)
    sin necesidad de credenciales estáticas en .env. En desarrollo local permite
    credenciales estándar de AWS (~/.aws/credentials o variables de entorno).
    """
    bucket = get_bucket_name()
    if not bucket:
        raise AppError(
            code=ErrorCodes.STORAGE_MISCONFIGURED,
            message="El servicio de almacenamiento AWS S3 no está configurado.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"missing": ["AWS_S3_BUCKET"]},
        )

    region = get_aws_region()
    endpoint_url = os.getenv("AWS_S3_ENDPOINT_URL") or os.getenv("R2_ENDPOINT_URL") or AWS_S3_ENDPOINT_URL
    access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")

    client_kwargs: dict = {"region_name": region}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key
        if session_token:
            client_kwargs["aws_session_token"] = session_token

    return boto3.client("s3", **client_kwargs)


def _clean_public_host() -> str:
    return get_public_host()


ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}


def _ext_from_content_type(content_type: str) -> str:
    try:
        return ALLOWED_IMAGE_CONTENT_TYPES[content_type]
    except KeyError as exc:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="El content_type no está permitido para subir imágenes.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"content_type": content_type, "allowed": sorted(ALLOWED_IMAGE_CONTENT_TYPES.keys())},
        ) from exc


def is_pending_key(file_key: str, *, namespace: str | None = None) -> bool:
    if namespace is not None:
        return file_key.startswith(_get_pending_prefix(namespace))
    return any(file_key.startswith(_get_pending_prefix(name)) for name in _NAMESPACE_PREFIXES)


def _detect_namespace_from_pending_key(file_key: str) -> str | None:
    for namespace in _NAMESPACE_PREFIXES:
        if file_key.startswith(_get_pending_prefix(namespace)):
            return namespace
    return None


def extract_file_key_from_public_url(image_url: str | None) -> str | None:
    if not image_url:
        return None

    public_host = _clean_public_host()
    if not public_host:
        return None

    normalized = image_url.strip()
    prefix = public_host + "/"
    if not normalized.startswith(prefix):
        return None

    return unquote(normalized[len(prefix) :])


def build_public_url(file_key: str) -> str:
    public_host = _clean_public_host()
    if public_host:
        return f"{public_host}/{file_key}"

    s3_client = _get_s3_client()
    bucket = get_bucket_name()
    try:
        return s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": file_key},
            ExpiresIn=3600,
        )
    except (ClientError, BotoCoreError) as exc:
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible generar la URL de lectura en AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "generate_presigned_get"},
        ) from exc


def object_exists(file_key: str) -> bool:
    s3_client = _get_s3_client()
    bucket = get_bucket_name()
    try:
        s3_client.head_object(Bucket=bucket, Key=file_key)
        return True
    except ClientError as exc:
        response = exc.response or {}
        error_code = str((response.get("Error") or {}).get("Code") or "")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible validar la imagen en AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "head_object"},
        ) from exc
    except BotoCoreError as exc:
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible conectar con AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "head_object"},
        ) from exc


def _head_object(file_key: str) -> dict:
    s3_client = _get_s3_client()
    bucket = get_bucket_name()
    try:
        return s3_client.head_object(Bucket=bucket, Key=file_key)
    except ClientError as exc:
        response = exc.response or {}
        error_code = str((response.get("Error") or {}).get("Code") or "")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise AppError(
                code=ErrorCodes.VALIDATION_ERROR,
                message="La imagen indicada no existe o ya expiro.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"file_key": file_key},
            ) from exc
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible validar la imagen en AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "head_object"},
        ) from exc
    except BotoCoreError as exc:
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible conectar con AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "head_object"},
        ) from exc


def _validate_uploaded_image(file_key: str) -> None:
    metadata = _head_object(file_key)
    content_length = int(metadata.get("ContentLength") or 0)
    content_type = str(metadata.get("ContentType") or "")

    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        try:
            delete_object(file_key)
        except AppError:
            pass
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="La imagen subida no tiene un tipo permitido.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"content_type": content_type, "file_key": file_key},
        )

    if content_length <= 0 or content_length > settings.upload_max_image_size_bytes:
        try:
            delete_object(file_key)
        except AppError:
            pass
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="La imagen subida excede el tamaño maximo permitido.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "file_key": file_key,
                "content_length": content_length,
                "max_allowed": settings.upload_max_image_size_bytes,
            },
        )


def promote_pending_object(pending_key: str, *, namespace: str | None = None) -> str:
    resolved_namespace = namespace or _detect_namespace_from_pending_key(pending_key)
    if not resolved_namespace:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="La imagen indicada no pertenece al espacio temporal esperado.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"file_key": pending_key},
        )

    pending_prefix = _get_pending_prefix(resolved_namespace)
    if not pending_key.startswith(pending_prefix):
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="La imagen indicada no pertenece al espacio temporal esperado.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"file_key": pending_key, "namespace": resolved_namespace},
        )

    if not object_exists(pending_key):
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="La imagen indicada no existe o ya expiró.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"file_key": pending_key},
        )

    _validate_uploaded_image(pending_key)

    final_key = _get_namespace_prefix(resolved_namespace) + pending_key[len(pending_prefix) :]
    s3_client = _get_s3_client()
    bucket = get_bucket_name()
    try:
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": pending_key},
            Key=final_key,
        )
        s3_client.delete_object(Bucket=bucket, Key=pending_key)
        return final_key
    except (ClientError, BotoCoreError) as exc:
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible confirmar la imagen en AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "promote_object"},
        ) from exc


def delete_object(file_key: str) -> None:
    if not file_key.startswith(tuple(_NAMESPACE_PREFIXES.values())):
        return

    s3_client = _get_s3_client()
    bucket = get_bucket_name()
    try:
        s3_client.delete_object(Bucket=bucket, Key=file_key)
    except (ClientError, BotoCoreError) as exc:
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible eliminar la imagen en AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "delete_object"},
        ) from exc


def cleanup_pending_image_from_public_url(image_url: str | None) -> bool:
    file_key = extract_file_key_from_public_url(image_url)
    if not file_key or not is_pending_key(file_key):
        return False

    try:
        delete_object(file_key)
        return True
    except AppError:
        return False


def generate_presigned_upload_url(content_type: str, *, namespace: str = "events") -> dict:
    """
    Genera una URL temporal para que el cliente suba la imagen mediante el proxy de optimización
    que la almacena en Amazon S3.
    """
    ext = _ext_from_content_type(content_type)
    pending_prefix = _get_pending_prefix(namespace)
    file_key = f"{pending_prefix}{uuid.uuid4().hex}{ext}"

    base_router = "communities" if namespace == "comunidad" else "events"
    proxy_upload_url = f"/api/v1/{base_router}/proxy-upload?file_key={file_key}"

    result = {
        "upload_url": proxy_upload_url,
        "file_key": file_key,
        "public_url": build_public_url(file_key),
        "max_upload_size_bytes": settings.upload_max_image_size_bytes,
    }

    if not _clean_public_host():
        result["public_url_is_presigned"] = True

    return result
