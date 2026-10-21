"""Compila dist/Orbit.exe: un solo archivo que se instala solo al abrirlo.

Uso:   python construir.py
Antes: pip install -r requirements.txt pyinstaller
Descarga las herramientas de terceros (PresentMon, LibreHardwareMonitor, PawnIO) a vendor/ si faltan.
"""
import io
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(RAIZ, "vendor")
TRABAJO = os.path.join(tempfile.gettempdir(), "orbit_build")  # ruta corta: PyInstaller falla con rutas largas

DESCARGAS = {
    "PresentMon.exe": "https://github.com/GameTechDev/PresentMon/releases/download/v2.6.0/PresentMon-2.6.0-x64.exe",
    "PawnIO_setup.exe": "https://github.com/namazso/PawnIO.Setup/releases/download/2.2.0/PawnIO_setup.exe",
}
LHM_ZIP = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip"
LHM_SOBRAN = ("Aga.", "OxyPlot")  # partes de la interfaz de LHM que Orbit no usa


def descargar_vendor():
    os.makedirs(os.path.join(VENDOR, "lhm"), exist_ok=True)
    for nombre, url in DESCARGAS.items():
        destino = os.path.join(VENDOR, nombre)
        if not os.path.exists(destino):
            print("Descargando", nombre)
            urllib.request.urlretrieve(url, destino)
    if not os.path.exists(os.path.join(VENDOR, "lhm", "LibreHardwareMonitorLib.dll")):
        print("Descargando LibreHardwareMonitor")
        with zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(LHM_ZIP).read())) as z:
            for nombre in z.namelist():
                if nombre.endswith(".dll") and "/" not in nombre and not nombre.startswith(LHM_SOBRAN):
                    with open(os.path.join(VENDOR, "lhm", nombre), "wb") as f:
                        f.write(z.read(nombre))


def crear_icono():
    """El .ico se dibuja con el mismo código que el logo de la app."""
    from PIL import Image
    from PySide6.QtWidgets import QApplication
    sys.path.insert(0, RAIZ)
    from orbit import estilo
    app = QApplication.instance() or QApplication([])
    png = os.path.join(TRABAJO, "logo.png")
    estilo.pixmap_logo(256).save(png)
    ruta = os.path.join(TRABAJO, "orbit.ico")
    Image.open(png).save(ruta, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                      (256, 256)])
    del app
    return ruta


def main():
    os.makedirs(TRABAJO, exist_ok=True)
    descargar_vendor()
    icono = crear_icono()
    datos = [f"{os.path.join(VENDOR, 'PresentMon.exe')};vendor", f"{os.path.join(VENDOR, 'PawnIO_setup.exe')};vendor",
             f"{os.path.join(VENDOR, 'lhm')};vendor/lhm"]
    comando = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
               "--name", "Orbit", "--icon", icono,
               "--distpath", os.path.join(RAIZ, "dist"), "--workpath", os.path.join(TRABAJO, "build"),
               "--specpath", TRABAJO, "--paths", RAIZ]
    for dato in datos:
        comando += ["--add-data", dato]
    for modulo in ("tkinter", "numpy", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf"):
        comando += ["--exclude-module", modulo]
    comando.append(os.path.join(RAIZ, "orbit.pyw"))
    subprocess.run(comando, check=True, cwd=RAIZ)
    print("\nListo:", os.path.join(RAIZ, "dist", "Orbit.exe"))


if __name__ == "__main__":
    main()
