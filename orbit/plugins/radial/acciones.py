"""Acciones que ofrece la rueda: convertir, comprimir y extraer archivos."""
import os
import shutil
import subprocess
import winreg
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable

EXT_WORD = {".doc", ".docx", ".docm", ".rtf", ".odt"}
EXT_EXCEL = {".xls", ".xlsx", ".xlsm", ".ods", ".csv"}
EXT_PPT = {".ppt", ".pptx", ".pptm", ".odp"}
EXT_PDF = {".pdf"}
EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".ico"}
EXT_COMPRIMIDO = {".zip", ".rar", ".7z"}

# Colores de sistema de Apple
ROJO, AZUL, VERDE, MORADO, AMBAR, CIAN = "#FF453A", "#0A84FF", "#30D158", "#BF5AF2", "#FF9F0A", "#40C8E0"
SIN_VENTANA = subprocess.CREATE_NO_WINDOW


@dataclass
class Accion:
    nombre: str
    color: str
    funcion: Callable[[list], list]  # recibe las rutas, devuelve las rutas creadas
    descripcion: str = ""
    lenta: bool = False  # avisa al empezar (Office tarda unos segundos)


# ---------------------------------------------------------------- utilidades

def ruta_unica(ruta):
    """Si la ruta ya existe devuelve 'nombre (1).ext', 'nombre (2).ext'..."""
    base, ext = os.path.splitext(ruta)
    n = 1
    while os.path.exists(ruta):
        ruta = f"{base} ({n}){ext}"
        n += 1
    return ruta


def salida(origen, ext, sufijo=""):
    return ruta_unica(os.path.splitext(origen)[0] + sufijo + ext)


def salida_conjunta(rutas, ext):
    """Nombre para un archivo que junta varios elementos (zip, pdf de imágenes...)."""
    if len(rutas) == 1:
        ruta = rutas[0].rstrip("\\/")
        base = ruta if os.path.isdir(ruta) else os.path.splitext(ruta)[0]
    else:
        carpeta = os.path.dirname(rutas[0].rstrip("\\/"))
        base = os.path.join(carpeta, os.path.basename(carpeta.rstrip("\\/")) or "Archivos")
    return ruta_unica(base + ext)


def buscar_winrar():
    """Carpeta de instalación de WinRAR, o None si no está."""
    carpetas = []
    for raiz, clave in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WinRAR"),
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\WinRAR"),
                        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\WinRAR")):
        try:
            with winreg.OpenKey(raiz, clave) as k:
                for valor in ("exe64", "exe32"):
                    try:
                        carpetas.append(os.path.dirname(winreg.QueryValueEx(k, valor)[0]))
                    except OSError:
                        pass
        except OSError:
            pass
    carpetas += [r"C:\Program Files\WinRAR", r"C:\Program Files (x86)\WinRAR"]
    for carpeta in carpetas:
        if os.path.isfile(os.path.join(carpeta, "Rar.exe")):
            return carpeta
    return None


def tiene_office(programa):
    """True si está instalado el programa de Office ("Word", "Excel" o "PowerPoint")."""
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, programa + r".Application\CLSID"))
        return True
    except OSError:
        return False


def buscar_7zip():
    for exe in (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if os.path.isfile(exe):
            return exe
    return shutil.which("7z")


# ---------------------------------------------------------------- comprimir / extraer

def comprimir_zip(rutas):
    destino = salida_conjunta(rutas, ".zip")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for ruta in rutas:
            padre = os.path.dirname(ruta.rstrip("\\/"))
            if not os.path.isdir(ruta):
                z.write(ruta, os.path.basename(ruta))
                continue
            for raiz, carpetas, archivos in os.walk(ruta):
                if not carpetas and not archivos:
                    z.write(raiz, os.path.relpath(raiz, padre))  # carpeta vacía
                for nombre in archivos:
                    completo = os.path.join(raiz, nombre)
                    if completo != destino:
                        z.write(completo, os.path.relpath(completo, padre))
    return [destino]


def comprimir_rar(rutas):
    destino = salida_conjunta(rutas, ".rar")
    rar = os.path.join(buscar_winrar(), "Rar.exe")
    subprocess.run([rar, "a", "-ep1", "-r", "-idq", "-y", destino, *rutas],
                   check=True, creationflags=SIN_VENTANA)
    return [destino]


def comprimir_7z(rutas):
    destino = salida_conjunta(rutas, ".7z")
    subprocess.run([buscar_7zip(), "a", "-y", destino, *rutas],
                   check=True, creationflags=SIN_VENTANA, capture_output=True)
    return [destino]


def extraer(rutas):
    creadas = []
    for ruta in rutas:
        destino = ruta_unica(os.path.splitext(ruta)[0])
        os.makedirs(destino)
        _extraer_en(ruta, destino)
        # Si dentro solo había una carpeta, se saca para no quedar con "Carpeta\Carpeta\..."
        contenido = os.listdir(destino)
        if len(contenido) == 1 and os.path.isdir(os.path.join(destino, contenido[0])):
            temporal = ruta_unica(destino + "_tmp")
            os.rename(destino, temporal)
            final = ruta_unica(os.path.join(os.path.dirname(ruta), contenido[0]))
            shutil.move(os.path.join(temporal, contenido[0]), final)
            os.rmdir(temporal)
            destino = final
        creadas.append(destino)
    return creadas


def _extraer_en(ruta, destino):
    if ruta.lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as z:
            z.extractall(destino)
    elif buscar_winrar():
        subprocess.run([os.path.join(buscar_winrar(), "WinRAR.exe"), "x", "-ibck", "-y", ruta, destino + "\\"],
                       check=True, creationflags=SIN_VENTANA)
    else:
        subprocess.run([buscar_7zip(), "x", "-y", f"-o{destino}", ruta],
                       check=True, creationflags=SIN_VENTANA, capture_output=True)


# ---------------------------------------------------------------- Office

def _abrible(ruta):
    """Office no abre rutas de más de 259 caracteres y en ese caso devuelve None sin avisar."""
    ruta = os.path.abspath(ruta)
    if len(ruta) >= 259:
        raise RuntimeError("la ruta es demasiado larga para Office; mueve el archivo a una carpeta más corta")
    return ruta


def _abierto(objeto, ruta):
    if objeto is None:
        raise RuntimeError(f"Office no pudo abrir {os.path.basename(ruta)}")
    return objeto

@contextmanager
def office(programa, coleccion):
    """Abre una instancia invisible de Word/Excel/PowerPoint y la cierra al terminar."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = None
    try:
        app = win32com.client.DispatchEx(programa)
        yield app
    finally:
        # PowerPoint reutiliza la ventana que tengas abierta: solo se cierra si quedó vacía
        if app is not None and getattr(app, coleccion).Count == 0:
            app.Quit()
        app = None
        pythoncom.CoUninitialize()


def _word(rutas, ext, formato, **extra):
    creadas = []
    with office("Word.Application", "Documents") as word:
        word.Visible = False
        word.DisplayAlerts = 0
        for ruta in rutas:
            doc = _abierto(word.Documents.Open(_abrible(ruta), ConfirmConversions=False, ReadOnly=True,
                                               AddToRecentFiles=False, Visible=False), ruta)
            try:
                destino = salida(ruta, ext)
                doc.SaveAs2(destino, FileFormat=formato, **extra)
                creadas.append(destino)
            finally:
                doc.Close(SaveChanges=0)
    return creadas


def _excel(rutas, ext, formato):
    creadas = []
    with office("Excel.Application", "Workbooks") as excel:
        excel.Visible = False
        excel.DisplayAlerts = False
        for ruta in rutas:
            libro = _abierto(excel.Workbooks.Open(_abrible(ruta), UpdateLinks=0, ReadOnly=True), ruta)
            try:
                destino = salida(ruta, ext)
                if formato == "pdf":
                    libro.ExportAsFixedFormat(0, destino)
                else:
                    libro.SaveAs(destino, FileFormat=formato)
                creadas.append(destino)
            finally:
                libro.Close(SaveChanges=False)
    return creadas


def _powerpoint(rutas, ext, formato):
    creadas = []
    with office("PowerPoint.Application", "Presentations") as ppt:
        for ruta in rutas:
            pres = _abierto(ppt.Presentations.Open(_abrible(ruta), ReadOnly=True, Untitled=False, WithWindow=False), ruta)
            try:
                destino = salida(ruta, ext)
                pres.SaveAs(destino, formato)
                creadas.append(destino)
            finally:
                pres.Close()
    return creadas


# ---------------------------------------------------------------- imágenes

def _sin_transparencia(imagen):
    """JPG y PDF no admiten transparencia: se pone fondo blanco."""
    from PIL import Image
    if imagen.mode in ("RGBA", "LA") or (imagen.mode == "P" and "transparency" in imagen.info):
        imagen = imagen.convert("RGBA")
        fondo = Image.new("RGB", imagen.size, "white")
        fondo.paste(imagen, mask=imagen.getchannel("A"))
        return fondo
    return imagen.convert("RGB")


def _imagenes(rutas, ext, formato, **opciones):
    from PIL import Image
    creadas = []
    for ruta in rutas:
        with Image.open(ruta) as imagen:
            if formato == "JPEG":
                imagen = _sin_transparencia(imagen)
            elif imagen.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                imagen = imagen.convert("RGBA")
            destino = salida(ruta, ext)
            imagen.save(destino, formato, **opciones)
            creadas.append(destino)
    return creadas


def reducir_imagenes(rutas):
    from PIL import Image
    creadas = []
    for ruta in rutas:
        with Image.open(ruta) as imagen:
            formato = imagen.format
            pequena = imagen.resize((max(1, imagen.width // 2), max(1, imagen.height // 2)), Image.LANCZOS)
            destino = salida(ruta, os.path.splitext(ruta)[1], " (50%)")
            pequena.save(destino, formato)
            creadas.append(destino)
    return creadas


def imagenes_a_pdf(rutas):
    from PIL import Image
    paginas = []
    for ruta in sorted(rutas):
        with Image.open(ruta) as imagen:
            paginas.append(_sin_transparencia(imagen))
    destino = salida_conjunta(rutas, ".pdf")
    paginas[0].save(destino, "PDF", save_all=True, append_images=paginas[1:], resolution=100)
    return [destino]


# ---------------------------------------------------------------- qué ofrecer

MAX_ACCIONES = 8


def acciones_para(rutas):
    """Elige las opciones de la rueda según lo que se esté arrastrando."""
    hay_carpetas = any(os.path.isdir(r) for r in rutas)
    exts = {os.path.splitext(r)[1].lower() for r in rutas}
    winrar, siete = buscar_winrar(), buscar_7zip()
    word, excel, ppt = (tiene_office(p) for p in ("Word", "Excel", "PowerPoint"))

    def solo(grupo):
        return not hay_carpetas and exts <= grupo

    lista = []
    if word and solo(EXT_WORD):
        lista.append(Accion("PDF", ROJO, lambda r: _word(r, ".pdf", 17), "Word a PDF", True))
        if exts != {".docx"}:
            lista.append(Accion("DOCX", AZUL, lambda r: _word(r, ".docx", 16), "Guardar como .docx", True))
        lista.append(Accion("TXT", CIAN, lambda r: _word(r, ".txt", 7), "Solo el texto", True))
        if exts != {".odt"}:
            lista.append(Accion("ODT", VERDE, lambda r: _word(r, ".odt", 23), "OpenDocument", True))
    elif excel and solo(EXT_EXCEL):
        lista.append(Accion("PDF", ROJO, lambda r: _excel(r, ".pdf", "pdf"), "Excel a PDF", True))
        if exts != {".xlsx"}:
            lista.append(Accion("XLSX", VERDE, lambda r: _excel(r, ".xlsx", 51), "Guardar como .xlsx", True))
        if exts != {".csv"}:
            lista.append(Accion("CSV", CIAN, lambda r: _excel(r, ".csv", 62), "Hoja activa a CSV", True))
    elif ppt and solo(EXT_PPT):
        lista.append(Accion("PDF", ROJO, lambda r: _powerpoint(r, ".pdf", 32), "Presentación a PDF", True))
        if exts != {".pptx"}:
            lista.append(Accion("PPTX", AMBAR, lambda r: _powerpoint(r, ".pptx", 24), "Guardar como .pptx", True))
    elif word and solo(EXT_PDF):
        lista.append(Accion("Word", AZUL, lambda r: _word(r, ".docx", 16), "PDF a Word editable", True))
    elif solo(EXT_IMAGEN):
        lista.append(Accion("PDF", ROJO, imagenes_a_pdf, "Todas en un PDF"))
        for nombre, ext, formato, opciones in (("PNG", ".png", "PNG", {}),
                                               ("JPG", ".jpg", "JPEG", {"quality": 92}),
                                               ("WEBP", ".webp", "WEBP", {"quality": 90})):
            if not exts <= ({".jpg", ".jpeg"} if ext == ".jpg" else {ext}):
                lista.append(Accion(nombre, MORADO,
                                    lambda r, e=ext, f=formato, o=opciones: _imagenes(r, e, f, **o),
                                    f"Convertir a {nombre}"))
        lista.append(Accion("ICO", AMBAR, lambda r: _imagenes(r, ".ico", "ICO"), "Icono de Windows"))
        lista.append(Accion("50%", CIAN, reducir_imagenes, "Reducir a la mitad"))
    elif solo(EXT_COMPRIMIDO) and (exts == {".zip"} or winrar or siete):
        lista.append(Accion("Extraer", VERDE, extraer, "Extraer en una carpeta"))

    lista.append(Accion("ZIP", AMBAR, comprimir_zip, "Comprimir en .zip"))
    if winrar:
        lista.append(Accion("RAR", MORADO, comprimir_rar, "Comprimir con WinRAR"))
    if siete:
        lista.append(Accion("7z", CIAN, comprimir_7z, "Comprimir con 7-Zip"))
    return lista[:MAX_ACCIONES]
