"""El ayudante: una copia de Orbit que corre como administrador solo para leer FPS y temperaturas.

Se registra una vez (con el aviso de Windows) como tarea programada; después Orbit la arranca
sin volver a preguntar. Solo lee datos y los envía a Orbit por 127.0.0.1 (nunca sale del equipo).
"""
import logging
import os
import shutil
import subprocess
import sys

from . import rutas, sistema


def _lanzador():
    """Ejecutable y argumentos base para volver a abrir Orbit (el .exe o pythonw + orbit.pyw)."""
    if rutas.CONGELADO:
        return sys.executable, ""
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return (pythonw if os.path.exists(pythonw) else sys.executable), f'"{os.path.join(rutas.BASE, "orbit.pyw")}" '


def registrado():
    return rutas.CONGELADO and os.path.exists(rutas.EXE_AYUDANTE) and sistema.tarea_existe()


def iniciar():
    """Arranca el ayudante. Instalado: sin avisos. Desde el código fuente: pide permiso cada vez."""
    if registrado():
        return sistema.ejecutar_tarea()
    if not rutas.CONGELADO:
        exe, base = _lanzador()
        return sistema.ejecutar_como_admin(exe, base + "--sensores", esperar=False) is not None
    return False


def instalar(pawnio):
    """Pide permiso de administrador y registra el ayudante. Devuelve True si quedó listo."""
    exe, base = _lanzador()
    codigo = sistema.ejecutar_como_admin(exe, base + "--instalar-ayudante" + (" --pawnio" if pawnio else ""))
    logging.info("Instalar ayudante -> %s", codigo)
    return codigo == 0


def quitar():
    exe, base = _lanzador()
    return sistema.ejecutar_como_admin(exe, base + "--quitar-ayudante") == 0


# ---------------------------------------------------------------- lo que corre ya elevado

def _cerrar_copias_del_ayudante():
    import psutil
    for proceso in psutil.process_iter(["exe"]):
        try:
            if proceso.info["exe"] and os.path.normcase(proceso.info["exe"]) == os.path.normcase(rutas.EXE_AYUDANTE):
                proceso.kill()
        except (psutil.Error, OSError):
            pass


def instalar_elevado(pawnio):
    if rutas.CONGELADO:
        _cerrar_copias_del_ayudante()
        os.makedirs(rutas.CARPETA_AYUDANTE, exist_ok=True)
        shutil.copy2(sys.executable, rutas.EXE_AYUDANTE)
        if not sistema.crear_tarea_admin(rutas.TAREA_AYUDANTE, rutas.EXE_AYUDANTE, "--sensores",
                                         "Orbit: lee FPS y temperaturas para el Medidor FPS. Solo lectura."):
            return 2
    if pawnio and not sistema.pawnio_instalado():
        subprocess.run([rutas.PAWNIO_SETUP, "-install", "-silent"], creationflags=sistema.SIN_VENTANA)
        if not sistema.pawnio_instalado():
            return 3
    return 0


def quitar_elevado():
    sistema.borrar_tarea()
    _cerrar_copias_del_ayudante()
    shutil.rmtree(rutas.CARPETA_AYUDANTE, ignore_errors=True)
    return 0
