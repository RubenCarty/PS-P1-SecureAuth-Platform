import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


class ImageValidationError(ValueError):
    pass


@dataclass
class NormalizedImage:
    content: bytes
    content_type: str
    extension: str


def normalize_image(
    file_storage,
    max_bytes: int,
) -> NormalizedImage:
    raw = file_storage.stream.read(max_bytes + 1)

    if not raw:
        raise ImageValidationError(
            "La imagen está vacía."
        )

    if len(raw) > max_bytes:
        raise ImageValidationError(
            "La imagen supera el tamaño máximo permitido."
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected_format = probe.format
            probe.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ImageValidationError(
            "El archivo no es una imagen válida."
        ) from exc

    if detected_format not in ALLOWED_FORMATS:
        raise ImageValidationError(
            "Solo se permiten imágenes JPEG, PNG o WEBP."
        )

    try:
        with Image.open(io.BytesIO(raw)) as original:
            image = ImageOps.exif_transpose(original)
            image.load()

            width, height = image.size

            if width <= 0 or height <= 0:
                raise ImageValidationError(
                    "Las dimensiones de la imagen no son válidas."
                )

            if width * height > 20_000_000:
                raise ImageValidationError(
                    "La imagen tiene demasiados píxeles."
                )

            image.thumbnail((1600, 1600))

            content_type, extension = ALLOWED_FORMATS[
                detected_format
            ]

            output = io.BytesIO()

            if detected_format == "JPEG":
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")

                image.save(
                    output,
                    format="JPEG",
                    quality=86,
                    optimize=True,
                )

            elif detected_format == "PNG":
                image.save(
                    output,
                    format="PNG",
                    optimize=True,
                )

            elif detected_format == "WEBP":
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")

                image.save(
                    output,
                    format="WEBP",
                    quality=86,
                    method=6,
                )

    except ImageValidationError:
        raise
    except Exception as exc:
        raise ImageValidationError(
            "No se pudo procesar la imagen."
        ) from exc

    return NormalizedImage(
        content=output.getvalue(),
        content_type=content_type,
        extension=extension,
    )


class ProductImageStorage:
    def __init__(self):
        self.upload_folder = (
            Path(current_app.root_path)
            / "static"
            / "uploads"
        )

        self.upload_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    def configured(self) -> bool:
        # En desarrollo local siempre estará disponible.
        return True

    def upload(
        self,
        image: NormalizedImage,
    ) -> str:
        filename = (
            f"{uuid.uuid4().hex}."
            f"{image.extension}"
        )

        destination = (
            self.upload_folder
            / filename
        )

        destination.write_bytes(
            image.content
        )

        return filename

    def delete(
        self,
        filename: str | None,
    ) -> None:
        if not filename:
            return

        path = (
            self.upload_folder
            / filename
        )

        try:
            path.unlink()
        except FileNotFoundError:
            pass