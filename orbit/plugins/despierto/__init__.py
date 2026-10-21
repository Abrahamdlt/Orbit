"""Plugin Mantener despierto: el equipo no se suspende (ni apaga la pantalla, si quieres) mientras está activado."""
import ctypes
import logging
import math
import time

from PySide6.QtCore import QTimer

from ...estilo import Interruptor, Segmentado
from ...sistema import kernel32
from ...ui import Fila, grupo
from ..base import Plugin

ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x1, 0x2
kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
kernel32.SetThreadExecutionState.restype = ctypes.c_uint

DURACIONES = [30, 60, 120, 0]  # minutos; 0 = hasta que lo apagues
NOMBRES_DURACIONES = ["30 min", "1 h", "2 h", "Siempre"]


def texto_minutos(minutos):
    horas, resto = divmod(minutos, 60)
    if not horas:
        return f"{resto} min"
    return f"{horas} h {resto} min" if resto else f"{horas} h"


class PluginDespierto(Plugin):
    id = "despierto"
    nombre = "Mantener despierto"
    descripcion = ("Evita que el equipo se suspenda o apague la pantalla mientras lo necesitas: durante un rato o "
                   "hasta que lo apagues.")
    icono = "despierto"

    def __init__(self, app):
        super().__init__(app)
        # No sobrevive a un reinicio: al abrir Orbit el equipo vuelve a suspenderse con normalidad
        self.cfg["activo"] = False
        self.hasta = None  # hora (time.time) a la que se apaga solo; None = sin límite
        # Se mira la hora de verdad: un temporizador de Qt no cuenta el tiempo que el equipo estuvo suspendido
        self.reloj = QTimer(self, interval=20_000)
        self.reloj.timeout.connect(self._revisar)

    def _minutos(self):
        duracion = self.cfg.get("duracion", 60)
        return duracion if duracion in DURACIONES else 60

    def restante(self):
        """Minutos que faltan para apagarse, o None si es sin límite."""
        if self.hasta is None:
            return None
        return max(1, math.ceil((self.hasta - time.time()) / 60))

    def estado(self):
        if not self.activo:
            return "Desactivado"
        restante = self.restante()
        return f"Despierto · {texto_minutos(restante)}" if restante else "Despierto · sin límite"

    def iniciar(self):
        minutos = self._minutos()
        self.hasta = time.time() + minutos * 60 if minutos else None
        self._aplicar()
        self.reloj.start()

    def detener(self):
        self.reloj.stop()
        self.hasta = None
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    def _aplicar(self):
        estado = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | (ES_DISPLAY_REQUIRED if self.cfg.get("pantalla", True) else 0)
        if not kernel32.SetThreadExecutionState(estado):
            logging.warning("SetThreadExecutionState no aceptó %#x", estado)

    def _revisar(self):
        if self.activo and self.hasta is not None and time.time() >= self.hasta:
            self.app.fijar_activo(self, False)
            self.app.aviso.mostrar(self.icono, "Se acabó el tiempo", "El equipo ya puede suspenderse")

    def al_atajo(self):
        self.app.fijar_activo(self, not self.activo)
        if self.activo:
            restante = self.restante()
            detalle = f"Durante {texto_minutos(restante)}" if restante else "Hasta que lo apagues"
        else:
            detalle = "El equipo ya puede suspenderse"
        self.app.aviso.mostrar(self.icono, self.nombre if self.activo else "Ya no está despierto", detalle)

    # --- ajustes
    def grupos_ajustes(self):
        duracion = Segmentado(NOMBRES_DURACIONES)
        duracion.fijar(DURACIONES.index(self._minutos()))
        duracion.cambiado.connect(self._duracion)
        pantalla = Interruptor()
        pantalla.fijar(self.cfg.get("pantalla", True))
        pantalla.toggled.connect(self._pantalla)
        return [grupo(Fila("Duración", "Al terminar se apaga solo y te avisa. «Siempre» dura hasta que lo apagues.",
                           duracion),
                      Fila("Mantener la pantalla encendida", "Si está apagado, solo se evita que el equipo se "
                                                             "suspenda: la pantalla se apaga como siempre.", pantalla),
                      titulo="Mientras está activado"),
                grupo(Fila("Al reiniciar", "Al cerrar Orbit o reiniciar el equipo, todo vuelve a la normalidad: "
                                           "no se queda despierto sin que lo sepas."), titulo="Cómo funciona")]

    def _duracion(self, indice):
        self.guardar(duracion=DURACIONES[indice])
        if self.activo:  # la cuenta empieza otra vez con la duración nueva
            self.iniciar()
            self.app.cambio.emit()

    def _pantalla(self, valor):
        self.guardar(pantalla=valor)
        if self.activo:
            self._aplicar()
