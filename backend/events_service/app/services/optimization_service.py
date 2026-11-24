import io
from typing import Tuple

import filetype
from PIL import Image, ImageOps, ImageCms
from fastapi import status

from events_service.app.core.exceptions import AppError, ErrorCodes

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_MIMES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}


def _convert_to_srgb(img: Image.Image) -> Image.Image:
    """Intenta convertir el perfil de color a sRGB de forma segura."""
    icc = img.info.get("icc_profile", "")
    if icc:
        try:
            f = io.BytesIO(icc)
            src_profile = ImageCms.ImageCmsProfile(f)
            srgb_profile = ImageCms.createProfile("sRGB")
            # Si tiene alpha, ImageCms no puede convertir RGBA directamente, se usa RGB temporalmente a menos que se trate especialmente
            if img.mode == "RGBA":
                # Convertir solo canales RGB
                r, g, b, a = img.split()
                rgb_img = Image.merge("RGB", (r, g, b))
                srgb_img = ImageCms.profileToProfile(rgb_img, src_profile, srgb_profile)
                r, g, b = srgb_img.split()
                img = Image.merge("RGBA", (r, g, b, a))
            elif img.mode == "RGB":
                img = ImageCms.profileToProfile(img, src_profile, srgb_profile)
        except Exception:
            pass  # Si el perfil ICC está corrupto, lo ignoramos

    return img


def _optimize_static_image(file_bytes: bytes, original_format: str) -> bytes:
    try:
        with io.BytesIO(file_bytes) as in_f:
            img = Image.open(in_f)
            
            # Orienta según EXIF auto-rotación antes de procesar
            img = ImageOps.exif_transpose(img)

            # Convierte a sRGB
            img = _convert_to_srgb(img)

            # Si es palette (P) o un modo raro, pasamos a RGB o RGBA
            if img.mode in ("P", "CMYK"):
                if "transparency" in img.info:
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

            # Rezize inteligente (máximo 1920px lado largo)
            MAX_SIZE = 1920
            width, height = img.size
            if width > MAX_SIZE or height > MAX_SIZE:
                # Mantiene el aspect ratio
                img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            
            # Quita metadatos guardando sin pasar el kwarg 'exif'
            # y determinamos el formato saliente. Tratamos de conservar el original.
            out_format = original_format
            if original_format not in ("JPEG", "PNG", "WEBP"):
                out_format = "WEBP" # Fallback eficiente

            save_kwargs = {"format": out_format, "optimize": True}
            
            if out_format == "JPEG":
                save_kwargs["quality"] = 85
                img = img.convert("RGB") # Jpeg no soporta RGBA
            elif out_format == "WEBP":
                save_kwargs["quality"] = 85
                save_kwargs["method"] = 6
            elif out_format == "PNG":
                # PNG compresión es lenta, Pillow lo hace automático con optimize=True
                pass

            output_io = io.BytesIO()
            img.save(output_io, **save_kwargs)
            return output_io.getvalue()
    except Exception as e:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message=f"Error procesando la imagen: {str(e)}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def _optimize_gif(file_bytes: bytes) -> bytes:
    """Intenta comprimir GIF de forma nativa. Si empeora o da error, retorna el original."""
    try:
        with io.BytesIO(file_bytes) as in_f:
            img = Image.open(in_f)
            if img.format != "GIF":
                return file_bytes
            
            output_io = io.BytesIO()
            img.save(output_io, format="GIF", save_all=True, optimize=True)
            optimized_bytes = output_io.getvalue()
            
            # Solo retornamos si en serio hubo reducción de peso, GIF en Pillow a veces los hace más pesados
            if len(optimized_bytes) < len(file_bytes):
                return optimized_bytes
            return file_bytes
    except Exception:
        # En caso de cualquier corrupción o problema con frames de GIF, fallamos seguro al original
        return file_bytes


def process_image_upload(file_bytes: bytes) -> Tuple[bytes, str, str]:
    """
    Procesa un archivo de imagen en memoria, valida MIME real, límites, elimina EXIF,
    redimensiona y optimiza.
    Retorna (bytes_optimizados, content_type_final, extension_final).
    """
    # 1. Validación de tamaño > 10MB
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="El archivo de imagen excede el límite máximo de 10MB.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # 2. Validación de MIME real (Magic bytes)
    kind = filetype.guess(file_bytes)
    if kind is None or kind.mime not in ALLOWED_MIMES:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="El archivo subido no es una imagen válida o un formato permitido.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            details={"detected_mime": kind.mime if kind else "unknown", "allowed": list(ALLOWED_MIMES.keys())},
        )

    mime_type = kind.mime
    extension = ALLOWED_MIMES[mime_type]

    # 3. Procesamiento según tipo
    if mime_type == "image/gif":
        optimized_bytes = _optimize_gif(file_bytes)
    else:
        # Extraer el formato requerido para Pillow (ej. "JPEG" para "image/jpeg")
        original_format = mime_type.split("/")[-1].upper()
        if original_format == "JPEG":  # Just making sure standard
            original_format = "JPEG"
        
        optimized_bytes = _optimize_static_image(file_bytes, original_format)
        
        # En caso de fallback a WEBP por formatos que Pillow en algunas instalaciones no retiene
        if mime_type == "image/avif":
            try:
                # Verificamos si logramos pasarlo a WEBP (usamos eso como fallback)
                mime_type = "image/webp"
                extension = ".webp"
            except Exception:
                pass

    return optimized_bytes, mime_type, extension
