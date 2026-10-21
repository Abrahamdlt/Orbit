"""Dónde vive cada cosa: instalación, datos del usuario y herramientas incluidas."""
import os
import sys

CONGELADO = getattr(sys, "frozen", False)  # True cuando corre como Orbit.exe
# Carpeta con los recursos incluidos (vendor/): dentro del .exe o la raíz del repositorio
BASE = sys._MEIPASS if CONGELADO else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(BASE, "vendor")
PRESENTMON = os.path.join(VENDOR, "PresentMon.exe")
LHM = os.path.join(VENDOR, "lhm")
PAWNIO_SETUP = os.path.join(VENDOR, "PawnIO_setup.exe")

DATOS = os.path.join(os.environ["APPDATA"], "Orbit")  # config y registro de errores
CONFIG = os.path.join(DATOS, "config.json")
LOG = os.path.join(DATOS, "orbit.log")

INSTALACION = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Orbit")
EXE_INSTALADO = os.path.join(INSTALACION, "Orbit.exe")
# El ayudante con permisos de administrador vive en Archivos de programa:
# ahí solo un administrador puede reemplazarlo
CARPETA_AYUDANTE = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Orbit")
EXE_AYUDANTE = os.path.join(CARPETA_AYUDANTE, "Orbit.exe")
TAREA_AYUDANTE = r"\Orbit\Sensores"

PROGRAMAS_MENU = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
ACCESO_INICIO = os.path.join(PROGRAMAS_MENU, "Startup", "Orbit.lnk")
ACCESO_MENU = os.path.join(PROGRAMAS_MENU, "Orbit.lnk")

PUERTO_DATOS = 47613      # el ayudante envía aquí las lecturas
PUERTO_AYUDANTE = 47614   # la app le avisa al ayudante que sigue viva
PUERTO_INSTANCIA = 47615  # una segunda copia de Orbit le pide a la primera que se muestre


def esta_instalado_aqui():
    """True si este proceso es el Orbit.exe instalado (no el descargado)."""
    return CONGELADO and os.path.normcase(sys.executable) in (os.path.normcase(EXE_INSTALADO),
                                                              os.path.normcase(EXE_AYUDANTE))
