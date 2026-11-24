from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from auth import models  # noqa: F401  # asegura registro de modelos
from auth.api.router import api_router
from auth.core.middleware import setup_middlewares
from auth.core.settings import settings
from auth.core.exceptions import AppError, ErrorCodes
from auth.core.trace import get_trace_id
from auth.schemas.common import ApiErrorData, ApiErrorResponse


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    setup_middlewares(app, settings)

    # Routers
    app.include_router(api_router)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        trace_id = get_trace_id(request)
        payload = ApiErrorResponse(
            message=exc.message,
            data=ApiErrorData(code=exc.code, details=exc.details, trace_id=trace_id),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        trace_id = get_trace_id(request)
        message = str(exc.detail) if exc.detail else "Error"

        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code = ErrorCodes.UNAUTHORIZED
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code = ErrorCodes.FORBIDDEN
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            code = ErrorCodes.EVENT_NOT_FOUND
        elif exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            code = ErrorCodes.VALIDATION_ERROR
        else:
            code = ErrorCodes.INTERNAL_ERROR if exc.status_code >= 500 else "HTTP_ERROR"

        payload = ApiErrorResponse(
            message=message,
            data=ApiErrorData(code=code, details=None, trace_id=trace_id),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = get_trace_id(request)
        
        error_msgs = []
        translated_details = []
        
        def translate_error(err_type: str, msg: str, ctx: dict | None = None) -> str:
            if "min_length" in err_type or err_type == "string_too_short":
                min_len = ctx.get("min_length", "") if ctx else ""
                return f"El texto debe tener al menos {min_len} caracteres." if min_len else "El texto es muy corto."
            elif "max_length" in err_type or err_type == "string_too_long":
                max_len = ctx.get("max_length", "") if ctx else ""
                return f"El texto no puede exceder los {max_len} caracteres." if max_len else "El texto es demasiado largo."
            elif err_type == "missing":
                return "Este campo es obligatorio."
            elif "value_error" in err_type:
                return msg
            elif "int_parsing" in err_type or "int_type" in err_type:
                return "Debe proveerse un número válido."
            elif "datetime" in err_type:
                return "Debe proveerse una fecha y hora válidas."
            elif "string_type" in err_type:
                return "El valor debe ser una cadena de texto."
            return "El valor provisto no es correcto." if "Input should be" in msg or "String should have" in msg else msg

        for err in exc.errors():
            field_path = " -> ".join(str(p) for p in err["loc"] if p != "body")
            field_path = field_path if field_path else "Cuerpo de la petición"
            
            translated_msg = translate_error(err.get("type", ""), err.get("msg", ""), err.get("ctx", {}))
            
            err_copy = {
                "type": err.get("type"),
                "loc": err.get("loc"),
                "msg": translated_msg,
                "input": str(err.get("input")) if err.get("input") is not None else None,
            }
            translated_details.append(err_copy)
            
            error_msgs.append(f"{field_path}: {translated_msg}")
            
        custom_message = "Errores de validación: " + " | ".join(error_msgs) if error_msgs else "Solicitud inválida. Revisa los campos enviados."

        payload_response = ApiErrorResponse(
            message=custom_message,
            data=ApiErrorData(code=ErrorCodes.VALIDATION_ERROR, details=translated_details, trace_id=trace_id),
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload_response.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = get_trace_id(request)
        payload = ApiErrorResponse(
            message="Ocurrió un error inesperado.",
            data=ApiErrorData(code=ErrorCodes.INTERNAL_ERROR, details=None, trace_id=trace_id),
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())

    # Backward compatible: mantener raíz para smoke test
    @app.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {"service": settings.app_name, "env": settings.app_env}

    return app


app = create_app()
