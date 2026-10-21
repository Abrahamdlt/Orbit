"""Orbit: el icono de la bandeja, sus plugins, los atajos y las ventanas."""
import logging
import os
import shutil
import socket
import subprocess
import sys

from PySide6.QtCore import QObject, QSocketNotifier, Signal
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import ayudante, estilo, rutas, sistema
from .atajos import Atajos
from .config import Config
from .dialogos import confirmar, informar
from .panel import Panel
from .plugins.fps import PluginFPS
from .plugins.radial import PluginRadial


class Orbit(QObject):
    cambio = Signal()  # algo cambió: el panel y los ajustes se refrescan

    def __init__(self):
        super().__init__()
        self.qapp = QApplication.instance() or QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.setFont(estilo.fuente(10))
        self.config = Config()
        estilo.BAJO_CONSUMO = self.config["bajo_consumo"]
        self.aviso = estilo.Aviso()
        self.atajos = Atajos()
        self.atajos.disparado.connect(self._atajo)
        self.atajo_ok = {}
        self.ventana_ajustes = None

        self.plugins = [PluginRadial(self), PluginFPS(self)]
        for plugin in self.plugins:
            if plugin.instalado:
                self.atajo_ok[plugin.id] = self.atajos.registrar(plugin.id, plugin.cfg["atajo"])
            if plugin.activo:
                self._con_cuidado(plugin.iniciar)

        self.panel = Panel(self)
        self.bandeja = QSystemTrayIcon(estilo.icono_orbit())
        self.bandeja.setToolTip("Orbit")
        self.bandeja.activated.connect(lambda _: self.panel.alternar(self.bandeja.geometry()))
        self.bandeja.show()
        self.cambio.connect(self._refrescar)
        self._escuchar_otras_copias()

        if "--recien-instalada" in sys.argv:
            self.aviso.mostrar("general", "Orbit está lista", "Haz clic en su icono junto al reloj")

    # --- plugins
    def _con_cuidado(self, funcion):
        try:
            funcion()
        except Exception:
            logging.exception("Error en un plugin")

    def plugin(self, clave):
        return next(p for p in self.plugins if p.id == clave)

    def fijar_activo(self, plugin, activo):
        if activo and not plugin.instalado:
            self.instalar_plugin(plugin)
            return
        if activo == plugin.activo:
            return
        plugin.cfg["activo"] = activo
        self.config.guardar()
        self._con_cuidado(plugin.iniciar if activo else plugin.detener)
        self.cambio.emit()

    def reiniciar_plugin(self, plugin):
        if plugin.activo:
            self._con_cuidado(plugin.detener)
            self._con_cuidado(plugin.iniciar)
        self.cambio.emit()

    def instalar_plugin(self, plugin):
        if plugin.requiere_admin and not confirmar(
                f"Añadir {plugin.nombre}", plugin.motivo_admin + "\n\nA continuación Windows te pedirá permiso.",
                "Continuar"):
            self.cambio.emit()
            return
        if not plugin.instalar():
            informar("No se añadió", f"{plugin.nombre} necesita el permiso de administrador para funcionar. "
                                     "Puedes intentarlo otra vez cuando quieras.")
            self.cambio.emit()
            return
        plugin.cfg.update(instalado=True, activo=True)
        self.config.guardar()
        self.atajo_ok[plugin.id] = self.atajos.registrar(plugin.id, plugin.cfg["atajo"])
        self._con_cuidado(plugin.iniciar)
        self.cambio.emit()

    def fijar_atajo(self, plugin, atajo):
        plugin.cfg["atajo"] = atajo
        self.config.guardar()
        self.atajo_ok[plugin.id] = self.atajos.registrar(plugin.id, atajo)
        self.cambio.emit()

    def _atajo(self, clave):
        plugin = self.plugin(clave)
        if plugin.instalado:
            self.fijar_activo(plugin, not plugin.activo)
            self.aviso.mostrar(plugin.icono, plugin.nombre, "Activado" if plugin.activo else "Desactivado")

    def _refrescar(self):
        self.panel.refrescar()
        if self.ventana_ajustes:
            self.ventana_ajustes.refrescar()

    # --- ventanas
    def abrir_ajustes(self, clave=None):
        from .ajustes import VentanaAjustes
        if self.ventana_ajustes is None or self.ventana_ajustes.paleta != estilo.paleta():
            if self.ventana_ajustes:
                self.ventana_ajustes.deleteLater()
            self.ventana_ajustes = VentanaAjustes(self)
        if clave:
            self.ventana_ajustes.ir_a(clave)
        self.ventana_ajustes.showNormal()
        self.ventana_ajustes.raise_()
        self.ventana_ajustes.activateWindow()

    def _escuchar_otras_copias(self):
        """Si abres Orbit otra vez (menú Inicio), la copia que ya corre muestra sus ajustes."""
        try:
            self.socket_instancia = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket_instancia.bind(("127.0.0.1", rutas.PUERTO_INSTANCIA))
            self.socket_instancia.setblocking(False)
            self.notificador = QSocketNotifier(self.socket_instancia.fileno(), QSocketNotifier.Read, self)
            self.notificador.activated.connect(self._mensaje_de_otra_copia)
        except OSError:
            logging.exception("No se pudo escuchar a otras copias")

    def _mensaje_de_otra_copia(self):
        try:
            self.socket_instancia.recv(64)
        except OSError:
            return
        self.abrir_ajustes()

    # --- general
    def fijar_inicio_con_windows(self, activar):
        self.config["iniciar_con_windows"] = activar
        self.config.guardar()
        if activar:
            if rutas.CONGELADO:
                sistema.crear_acceso(rutas.ACCESO_INICIO, sys.executable)
            else:
                pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                sistema.crear_acceso(rutas.ACCESO_INICIO, pythonw, f'"{os.path.join(rutas.BASE, "orbit.pyw")}"')
        else:
            sistema.borrar_archivo(rutas.ACCESO_INICIO)

    def fijar_bajo_consumo(self, activar):
        self.config["bajo_consumo"] = activar
        self.config.guardar()
        estilo.BAJO_CONSUMO = activar
        for plugin in self.plugins:
            if plugin.activo and hasattr(plugin, "aplicar_ritmo"):
                plugin.aplicar_ritmo()
        self.cambio.emit()

    def desinstalar(self):
        if not confirmar("Desinstalar Orbit", "Se quitarán Orbit, sus plugins y sus ajustes de este equipo."
                         + (" Windows te pedirá permiso para quitar el ayudante del Medidor FPS."
                            if ayudante.registrado() else ""), "Desinstalar", peligro=True):
            return
        if ayudante.registrado():
            ayudante.quitar()
        for ruta in (rutas.ACCESO_INICIO, rutas.ACCESO_MENU):
            sistema.borrar_archivo(ruta)
        shutil.rmtree(rutas.DATOS, ignore_errors=True)
        # El .exe no puede borrarse a sí mismo mientras corre: lo borra una consola oculta tras cerrarse
        subprocess.Popen(f'cmd /c timeout /t 3 /nobreak >nul & rmdir /s /q "{rutas.INSTALACION}"',
                         creationflags=sistema.SIN_VENTANA)
        self.salir()

    def salir(self):
        for plugin in self.plugins:
            if plugin.activo:
                self._con_cuidado(plugin.detener)
        self.bandeja.hide()
        self.qapp.quit()

    def correr(self):
        return self.qapp.exec()


def main():
    os.makedirs(rutas.DATOS, exist_ok=True)
    logging.basicConfig(filename=rutas.LOG, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    argumentos = sys.argv[1:]
    if "--sensores" in argumentos:
        from .plugins.fps import medicion
        return medicion.correr()
    if "--instalar-ayudante" in argumentos:
        return ayudante.instalar_elevado("--pawnio" in argumentos)
    if "--quitar-ayudante" in argumentos:
        return ayudante.quitar_elevado()
    if rutas.CONGELADO and not rutas.esta_instalado_aqui():
        from .instalador import correr
        return correr()
    if not sistema.una_sola_instancia("Orbit_UnaSolaInstancia"):
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"mostrar", ("127.0.0.1", rutas.PUERTO_INSTANCIA))
        return 0
    try:
        return Orbit().correr()
    except Exception:
        logging.exception("Orbit se cerró por un error")
        raise
