"""Reconocimiento de texto con el OCR que trae Windows (Windows.Media.Ocr): sin internet y sin nada que instalar.

Ojo: winrt se importa siempre dentro de las funciones, nunca al cargar Orbit. Así no ocupa memoria hasta que se
usa y, sobre todo, se carga después de PySide6: importar winrt antes que PySide6 cierra Python de golpe.
"""
import asyncio


class SinIdioma(Exception):
    """Windows no tiene ningún idioma de OCR instalado (o no el elegido)."""


def idiomas():
    """[(etiqueta, nombre)] de los idiomas que el OCR de Windows sabe leer en este equipo."""
    from winrt.windows.media.ocr import OcrEngine
    return [(idioma.language_tag, idioma.display_name) for idioma in OcrEngine.available_recognizer_languages]


def maximo():
    """Lado máximo de imagen que acepta el OCR de Windows (en píxeles)."""
    from winrt.windows.media.ocr import OcrEngine
    return OcrEngine.max_image_dimension


def reconocer(png, idioma=None, saltos=True):
    """Texto de una imagen PNG. Corre en un hilo aparte: la API de Windows es asíncrona."""
    return asyncio.run(_reconocer(png, idioma, saltos))


async def _reconocer(png, idioma, saltos):
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    if idioma:
        motor = OcrEngine.try_create_from_language(Language(idioma))
    else:
        motor = OcrEngine.try_create_from_user_profile_languages()
    if motor is None:
        raise SinIdioma(idioma or "")
    flujo = InMemoryRandomAccessStream()
    escritor = DataWriter(flujo)
    escritor.write_bytes(png)
    await escritor.store_async()
    escritor.detach_stream()
    flujo.seek(0)
    decodificador = await BitmapDecoder.create_async(flujo)
    imagen = await decodificador.get_software_bitmap_async()
    resultado = await motor.recognize_async(imagen)
    lineas = [linea.text for linea in resultado.lines]
    return "\n".join(lineas) if saltos else " ".join(lineas)
