"""Plugin Rueda radial: arrastra algo en el Explorador, pulsa Tab y suéltalo sobre una opción."""
import logging
import os
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor

from ... import estilo, sistema
from ...dialogos import DialogoTecla
from ...estilo import Interruptor
from ...ui import Fila, grupo
from ..base import Plugin
from .rueda import GanchoTeclado, Rueda

# Programas en los que la tecla + arrastre abre la rueda (en el resto, la tecla funciona normal)
PROGRAMAS = {"explorer.exe"}


class _Puente(QObject):
    """Lleva el resultado del hilo de trabajo a la interfaz."""
    terminado = Signal(bool, str, str)


class PluginRadial(Plugin):
    id = "radial"
    nombre = "Rueda radial"
    descripcion = ("Arrastra un archivo o carpeta en el Explorador y pulsa Tab: aparece una rueda para "
                   "comprimirlo, convertirlo o extraerlo.")
    icono = "radial"

    def __init__(self, app):
        super().__init__(app)
        self.rueda = None
        self.gancho = None
        self.puente = _Puente()
        self.puente.terminado.connect(self._terminado)

    def estado(self):
        return f"{self.cfg['tecla_nombre']} al arrastrar" if self.activo else "Desactivado"

    def iniciar(self):
        if self.gancho:
            return
        if self.rueda is None:
            self.rueda = Rueda()
            self.rueda.accion_elegida.connect(self._ejecutar)
        self.gancho = GanchoTeclado(self.cfg["tecla_vk"], self._interceptar)
        self.gancho.tecla.connect(self._tecla)

    def detener(self):
        if self.gancho:
            self.gancho.quitar()
            self.gancho = None
        if self.rueda:
            self.rueda.ocultar()

    def _interceptar(self):
        if self.rueda.isVisible():
            return True  # la tecla otra vez cierra la rueda
        return sistema.boton_izquierdo_presionado() and sistema.programa_en_primer_plano() in PROGRAMAS

    def _tecla(self):
        if self.rueda.isVisible():
            self.rueda.ocultar()
        else:
            self.rueda.mostrar(QCursor.pos())

    def _ejecutar(self, accion, rutas):
        logging.info("Acción %s sobre %s", accion.nombre, rutas)
        if accion.lenta and self.cfg["notificaciones"]:
            self.app.aviso.mostrar("radial", accion.descripcion, "Trabajando…")

        def trabajo():
            try:
                creadas = accion.funcion(rutas)
                nombres = ", ".join(os.path.basename(c) for c in creadas[:2]) + ("…" if len(creadas) > 2 else "")
                self.puente.terminado.emit(True, "Listo", nombres)
            except Exception as error:
                logging.exception("Falló %s", accion.nombre)
                self.puente.terminado.emit(False, f"{accion.nombre}: no se pudo", str(error)[:80])

        threading.Thread(target=trabajo, daemon=True).start()

    def _terminado(self, ok, titulo, detalle):
        # Los errores se avisan siempre: si no, fallaría en silencio
        if not ok or self.cfg["notificaciones"]:
            self.app.aviso.mostrar("radial", titulo, detalle)

    # --- ajustes
    def grupos_ajustes(self):
        cambiar = estilo.boton(self.cfg["tecla_nombre"])
        fila_tecla = Fila("Tecla de la rueda", "Se pulsa mientras arrastras algo en el Explorador.", cambiar)

        def elegir_tecla():
            dialogo = DialogoTecla(self.cfg["tecla_nombre"])
            if dialogo.exec() and dialogo.vk:
                self.cfg.update(tecla_vk=dialogo.vk, tecla_nombre=dialogo.nombre)
                self.app.config.guardar()
                if self.gancho:
                    self.gancho.vk = dialogo.vk
                cambiar.setText(dialogo.nombre)
                self.app.cambio.emit()

        cambiar.clicked.connect(elegir_tecla)
        avisos = Interruptor()
        avisos.fijar(self.cfg["notificaciones"])

        def cambiar_avisos(valor):
            self.cfg["notificaciones"] = valor
            self.app.config.guardar()

        avisos.toggled.connect(cambiar_avisos)
        fila_avisos = Fila("Avisar al terminar", "Un aviso pequeño cuando termina. Los errores se avisan siempre.",
                           avisos)
        que_hace = Fila("Qué puede hacer",
                        "Word, Excel y PowerPoint a PDF y otros formatos (si hay Office) · Imágenes a PNG, JPG, "
                        "WEBP, ICO o PDF · Comprimir en ZIP (y RAR o 7z si están instalados) · Extraer .zip, "
                        ".rar y .7z")
        return [grupo(fila_tecla, fila_avisos, titulo="Rueda"), grupo(que_hace, titulo="Opciones de la rueda")]
