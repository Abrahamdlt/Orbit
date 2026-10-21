"""Lo que hace el ayudante (corre como administrador): FPS con PresentMon y temperaturas con
LibreHardwareMonitor. Envía una lectura cada medio segundo a Orbit por 127.0.0.1 y se cierra
solo si Orbit deja de avisar que sigue abierto."""
import collections
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time

from ... import rutas, sistema

# Segundos de cuadros que se promedian y cada cuánto se envía una lectura (normal / baja latencia)
VENTANA_FPS = {False: 1.0, True: 0.4}
ENVIO = {False: 0.5, True: 0.25}


class Fps:
    """Lee la salida de PresentMon y calcula los FPS de cada proceso."""

    def __init__(self):
        self.cuadros = collections.defaultdict(collections.deque)  # (pid, swapchain) -> (llegada, ms)
        self.nombres = {}
        self.bloqueo = threading.Lock()
        self.proceso = None

    def arrancar(self):
        self.proceso = subprocess.Popen(
            [rutas.PRESENTMON, "--output_stdout", "--no_console_stats", "--stop_existing_session",
             "--session_name", "OrbitFPS"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
            creationflags=sistema.SIN_VENTANA)
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self):
        columnas = None
        for linea in self.proceso.stdout:
            partes = linea.rstrip("\r\n").split(",")
            if columnas is None:
                if "Application" in partes and "ProcessID" in partes:
                    columnas = {nombre: i for i, nombre in enumerate(partes)}
                    i_app, i_pid = columnas["Application"], columnas["ProcessID"]
                    i_cadena = columnas.get("SwapChainAddress", i_pid)
                    i_ms = columnas.get("MsBetweenPresents", columnas.get("FrameTime"))
                continue
            try:
                pid, ms = int(partes[i_pid]), float(partes[i_ms])
            except (ValueError, IndexError, TypeError):
                continue
            if ms <= 0:
                continue
            ahora = time.monotonic()
            with self.bloqueo:
                cola = self.cuadros[(pid, partes[i_cadena])]
                cola.append((ahora, ms))
                while cola and ahora - cola[0][0] > 3:
                    cola.popleft()
                self.nombres[pid] = partes[i_app]
        logging.info("PresentMon terminó (código %s)", self.proceso.poll())

    def de(self, pid, ventana=VENTANA_FPS[False]):
        """FPS del proceso, o None si no está dibujando nada."""
        ahora, mejor = time.monotonic(), None
        with self.bloqueo:
            for (p, _), cola in self.cuadros.items():
                if p != pid or not cola or ahora - cola[-1][0] > 1.5:
                    continue
                total = cuenta = 0
                for _, ms in reversed(cola):
                    total += ms
                    cuenta += 1
                    if total >= ventana * 1000:
                        break
                fps = cuenta * 1000 / total
                mejor = fps if mejor is None else max(mejor, fps)
        return mejor

    def parar(self):
        if self.proceso and self.proceso.poll() is None:
            self.proceso.kill()


class Temperaturas:
    """CPU (y GPU si no es NVIDIA) con LibreHardwareMonitor. La CPU necesita el driver PawnIO."""

    def __init__(self):
        self.datos = {}
        self.computadora = None
        self.iniciado = False

    def arrancar(self):
        self.iniciado = True
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        try:
            sys.path.append(rutas.LHM)  # para que .NET encuentre las dependencias
            import clr
            clr.AddReference(os.path.join(rutas.LHM, "LibreHardwareMonitorLib.dll"))
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType
            self.computadora = Computer()
            self.computadora.IsCpuEnabled = True
            self.computadora.IsGpuEnabled = True
            self.computadora.Open()
            logging.info("LibreHardwareMonitor listo: %s", [hw.Name for hw in self.computadora.Hardware])
        except Exception:
            logging.exception("No se pudo abrir LibreHardwareMonitor")
            return
        prioridad_cpu = ("CPU Package", "Core (Tctl/Tdie)", "Core Max", "Core Average")
        while True:
            datos = {}
            for hw in self.computadora.Hardware:
                try:
                    hw.Update()
                except Exception:
                    continue
                temps = {s.Name: s.Value for s in hw.Sensors if s.SensorType == SensorType.Temperature and s.Value}
                if hw.HardwareType == HardwareType.Cpu:
                    for nombre in prioridad_cpu:
                        if nombre in temps:
                            datos["cpu_temp"] = float(temps[nombre])
                            break
                elif hw.HardwareType in (HardwareType.GpuNvidia, HardwareType.GpuAmd, HardwareType.GpuIntel):
                    cargas = {s.Name: s.Value for s in hw.Sensors if s.SensorType == SensorType.Load and s.Value}
                    if "GPU Core" in temps and "gpu_temp" not in datos:
                        datos["gpu_temp"] = float(temps["GPU Core"])
                    if "GPU Core" in cargas and "gpu_uso" not in datos:
                        datos["gpu_uso"] = float(cargas["GPU Core"])
            if datos.keys() != self.datos.keys():
                logging.info("Temperaturas disponibles: %s", sorted(datos))
            self.datos = datos
            time.sleep(1)


def correr():
    """Punto de entrada del ayudante (Orbit.exe --sensores)."""
    if not sistema.una_sola_instancia("Orbit_Ayudante"):
        return 0
    logging.info("Ayudante iniciado (admin=%s)", sistema.es_admin())
    entrada = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    entrada.bind(("127.0.0.1", rutas.PUERTO_AYUDANTE))
    entrada.settimeout(0.5)
    salida = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    fps, temperaturas = Fps(), Temperaturas()
    try:
        fps.arrancar()
    except OSError:
        logging.exception("No se pudo abrir PresentMon")

    pedido = {"t": True, "r": False}  # lo que Orbit necesita: temperaturas y baja latencia
    ultimo_aviso = ultimo_envio = time.monotonic()
    try:
        while time.monotonic() - ultimo_aviso < 6:  # Orbit avisa cada segundo que sigue abierta
            try:
                paquete = entrada.recv(256)
                ultimo_aviso = time.monotonic()
                try:
                    pedido.update(json.loads(paquete))
                except ValueError:
                    pass  # aviso simple de una versión anterior
            except socket.timeout:
                pass
            rapido = bool(pedido.get("r"))
            entrada.settimeout(0.05 if rapido else 0.25)
            if pedido.get("t") and not temperaturas.iniciado:
                temperaturas.arrancar()
            elif not pedido.get("t") and temperaturas.iniciado:
                logging.info("Temperaturas apagadas: el ayudante se cierra para liberar memoria")
                break  # .NET no se puede descargar: Orbit lo vuelve a abrir sin los sensores
            ahora = time.monotonic()
            if ahora - ultimo_envio >= ENVIO[rapido]:
                ultimo_envio = ahora
                pid = sistema.pid_en_primer_plano()
                lectura = dict(temperaturas.datos, fps=fps.de(pid, VENTANA_FPS[rapido]), app=fps.nombres.get(pid, ""))
                salida.sendto(json.dumps(lectura).encode(), ("127.0.0.1", rutas.PUERTO_DATOS))
    finally:
        fps.parar()
        logging.info("Ayudante cerrado")
    return 0
