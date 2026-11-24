import anyio
from fastapi import APIRouter, Request, status

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.services.optimization_service import process_image_upload
from events_service.app.services.storage_service import _get_s3_client, get_bucket_name, is_pending_key

router = APIRouter(tags=["storage"])


@router.put("/proxy-upload", status_code=status.HTTP_200_OK)
async def proxy_upload_file(request: Request, file_key: str):
    """
    Recibe la imagen cruda directamente del cliente, la optimiza con Pillow
    y la almacena en Amazon S3 bajo el prefijo temporal (pending/).
    """
    if not is_pending_key(file_key):
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="La llave destino no pertenece a un espacio temporal permitido.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"file_key": file_key},
        )

    file_bytes = await request.body()
    if not file_bytes:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="El cuerpo de la solicitud (archivo) no puede estar vacío.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        optimized_bytes, final_mime, _ = await anyio.to_thread.run_sync(
            process_image_upload, file_bytes
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message=f"Error al procesar la imagen de forma segura: {str(e)}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    s3_client = _get_s3_client()
    bucket_name = get_bucket_name()
    try:
        def _upload_to_s3():
            s3_client.put_object(
                Bucket=bucket_name,
                Key=file_key,
                Body=optimized_bytes,
                ContentType=final_mime,
                CacheControl="public, max-age=31536000, immutable",
            )

        await anyio.to_thread.run_sync(_upload_to_s3)

    except Exception as exc:
        raise AppError(
            code=ErrorCodes.STORAGE_UNAVAILABLE,
            message="No fue posible subir la imagen optimizada a AWS S3 en este momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": "aws_s3", "operation": "proxy_upload"},
        ) from exc

    return {"success": True, "message": "Imagen subida exitosamente a AWS S3", "storage": "aws_s3"}
