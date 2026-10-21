"""Lecturas que Orbit hace sola (uso de CPU, RAM y GPU NVIDIA) más las que manda el ayudante."""
import json
import logging
import socket
import time

import psutil
from PySide6.QtCore import QObject, QSocketNotifier, QTimer, Signal

from ... import ayudante, rutas

TEMPERATURAS = ("cpu_temp", "gpu_temp")


class Nvidia:
    """Temperatura y uso de GPU NVIDIA sin permisos de administrador (NVML, viene con el driver)."""

    def __init__(self):
        self.gpu = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml = pynvml
            self.gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            logging.info("Sin NVML: la GPU se leerá con el ayudante")

    def leer(self, temperaturas=True):
        if self.gpu is None:
            return {}
        try:
            datos = {"gpu_uso": float(self.nvml.nvmlDeviceGetUtilizationRates(self.gpu).gpu)}
            if temperaturas:
                datos["gpu_temp"] = float(self.nvml.nvmlDeviceGetTemperature(self.gpu,
                                                                             self.nvml.NVML_TEMPERATURE_GPU))
            return datos
        except Exception:
            return {}


class Lector(QObject):
    """Junta las lecturas y las emite: cada 250 ms (baja latencia), 1 s (normal) o 2 s (bajo consumo).
    El uso de CPU, RAM y GPU se lee cada 1 s (2 s en bajo consumo); solo el FPS va más rápido."""
    datos = Signal(dict)

    def __init__(self):
        super().__init__()
        self.nvidia = None
        self.del_ayudante, self.hora_ayudante = {}, 0.0
        self.ayudante_iniciado = False
        self.rapido, self.lento, self.temperaturas = False, False, True
        self._sistema, self._hora_sistema, self._ultimo_intento = {}, 0.0, 0.0
        self.reloj = QTimer(self, interval=1000)
        self.reloj.timeout.connect(self._leer)
        self.entrada = self.salida = self.notificador = None

    @property
    def ayudante_conectado(self):
        return time.monotonic() - self.hora_ayudante < 3

    def configurar(self, rapido, lento, temperaturas):
        self.rapido, self.lento, self.temperaturas = rapido, lento, temperaturas
        self.reloj.setInterval(250 if rapido else 2000 if lento else 1000)
        self._hora_sistema = 0.0  # relee el sistema en el próximo tic

    def arrancar(self):
        if self.reloj.isActive():
            return
        if self.nvidia is None:
            self.nvidia = Nvidia()
        try:
            self.entrada = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.entrada.bind(("127.0.0.1", rutas.PUERTO_DATOS))
            self.entrada.setblocking(False)
            self.notificador = QSocketNotifier(self.entrada.fileno(), QSocketNotifier.Read, self)
            self.notificador.activated.connect(self._recibir)
        except OSError:
            logging.exception("No se pudo escuchar al ayudante")
        self.salida = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        psutil.cpu_percent(None)
        self._ultimo_intento = time.monotonic()
        self.ayudante_iniciado = ayudante.iniciar()
        self.reloj.start()
        self._leer()

    def parar(self):
        self.reloj.stop()
        if self.notificador:
            self.notificador.setEnabled(False)
            self.notificador = None
        for s in (self.entrada, self.salida):
            if s:
                s.close()
        self.entrada = self.salida = None
        self.ayudante_iniciado = False  # sin avisos, el ayudante se cierra solo en unos segundos

    def _recibir(self):
        while True:
            try:
                paquete = self.entrada.recv(4096)
            except (BlockingIOError, OSError):
                return
            try:
                self.del_ayudante = json.loads(paquete)
                self.hora_ayudante = time.monotonic()
            except ValueError:
                pass

    def _avisar_al_ayudante(self, ahora):
        # Le dice que Orbit sigue abierta y qué necesita (temperaturas, baja latencia)
        try:
            pedido = json.dumps({"t": self.temperaturas, "r": self.rapido}).encode()
            self.salida.sendto(pedido, ("127.0.0.1", rutas.PUERTO_AYUDANTE))
        except OSError:
            pass
        # Si el ayudante se cerró (por ejemplo, al apagar las temperaturas), se vuelve a abrir
        if not self.ayudante_conectado and ahora - self._ultimo_intento > 6 and ayudante.registrado():
            self._ultimo_intento = ahora
            ayudante.iniciar()

    def _leer(self):
        ahora = time.monotonic()
        self._avisar_al_ayudante(ahora)
        if ahora - self._hora_sistema >= (1.9 if self.lento else 0.95):
            self._hora_sistema = ahora
            self._sistema = {"cpu_uso": psutil.cpu_percent(None), "ram_uso": psutil.virtual_memory().percent}
            self._sistema.update(self.nvidia.leer(self.temperaturas))
        lectura = {}
        ayudante_ok = self.ayudante_conectado
        if ayudante_ok:
            lectura.update({k: v for k, v in self.del_ayudante.items() if v is not None})
        lectura.update(self._sistema)
        if not self.temperaturas:
            for clave in TEMPERATURAS:
                lectura.pop(clave, None)
        lectura["ayudante"] = ayudante_ok
        self.datos.emit(lectura)
