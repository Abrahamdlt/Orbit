"""Plugin Siempre encima: el atajo fija la ventana que tienes delante por encima de las demás (o la suelta)."""
import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ... import estilo
from ...estilo import Interruptor
from ...ui import Fila, grupo
from ..base import Plugin
from . import ventanas
from .ventanas import Borde


def recortar(texto, largo=48):
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


class PluginEncima(Plugin):
    id = "encima"
    nombre = "Siempre encima"
    descripcion = ("Fija la ventana que tienes delante por encima de las demás, con un borde de color para "
                   "reconocerla. El mismo atajo la suelta.")
    icono = "encima"
    texto_atajo = "Fijar o soltar la ventana de delante"

    def __init__(self, app):
        super().__init__(app)
        self.fijadas = {}  # hwnd -> Borde (o None si no se muestra el borde)
        self.reloj = QTimer(self)
        self.reloj.timeout.connect(self._seguir)
        self._lista = None  # contenedor de la lista en Ajustes

    def estado(self):
        if not self.activo:
            return "Desactivado"
        n = len(self.fijadas)
        if not n:
            return self.cfg["atajo"]["texto"]
        return f"{n} ventana{'s' if n > 1 else ''} fijada{'s' if n > 1 else ''}"

    def detener(self):
        for hwnd in list(self.fijadas):
            self.soltar(hwnd, avisar=False)

    def al_atajo(self):
        if not self.activo:
            self.avisar_desactivado()
            return
        hwnd = ventanas.ventana_delante()
        if hwnd in self.fijadas:
            self.soltar(hwnd)
            return
        if not ventanas.se_puede_fijar(hwnd):
            self.app.aviso.mostrar(self.icono, self.nombre, "Elige primero una ventana")
            return
        if ventanas.esta_encima(hwnd):
            self.app.aviso.mostrar(self.icono, "Ya está siempre encima", "Esa ventana se fija sola")
            return
        error = ventanas.fijar(hwnd, True)
        if error:
            logging.info("No se pudo fijar %s (%s): error %s", ventanas.programa(hwnd), ventanas.clase(hwnd), error)
            detalle = "Esa ventana es de administrador" if error == ventanas.ERROR_ACCESS_DENIED else \
                "Windows no dejó fijar esa ventana"
            self.app.aviso.mostrar(self.icono, "No se pudo fijar", detalle)
            return
        self.fijadas[hwnd] = Borde() if self.cfg.get("borde", True) else None
        self._seguir()
        self._ritmo()
        self.app.aviso.mostrar(self.icono, "Fijada encima", recortar(ventanas.titulo(hwnd) or ventanas.programa(hwnd)))
        self._cambio()

    def soltar(self, hwnd, avisar=True):
        borde = self.fijadas.pop(hwnd, None)
        if borde:
            borde.hide()
            borde.deleteLater()
        if ventanas.existe(hwnd):
            ventanas.fijar(hwnd, False)
            if avisar:
                self.app.aviso.mostrar(self.icono, "Ya no está encima",
                                       recortar(ventanas.titulo(hwnd) or ventanas.programa(hwnd)))
        self._ritmo()
        self._cambio()

    def aplicar_ritmo(self):
        self._ritmo()

    def _ritmo(self):
        """Con borde, se sigue a la ventana 10 veces por segundo (4 en bajo consumo); sin borde, solo se mira
        de vez en cuando si se cerró."""
        if not self.fijadas:
            self.reloj.stop()
            return
        con_borde = any(self.fijadas.values())
        self.reloj.setInterval((250 if estilo.BAJO_CONSUMO else 100) if con_borde else 1000)
        self.reloj.start()

    def _seguir(self):
        for hwnd, borde in list(self.fijadas.items()):
            # Se cerró, o algo le quitó el «encima» por su cuenta: deja de estar fijada
            if not ventanas.existe(hwnd) or not ventanas.esta_encima(hwnd):
                self.soltar(hwnd, avisar=False)
            elif borde:
                borde.seguir(hwnd)

    def _cambio(self):
        self.app.cambio.emit()
        self._refrescar_lista()

    # --- ajustes
    def grupos_ajustes(self):
        borde = Interruptor()
        borde.fijar(self.cfg.get("borde", True))
        borde.toggled.connect(self._borde)
        self._lista = QWidget()
        diseno = QVBoxLayout(self._lista)
        diseno.setContentsMargins(0, 0, 0, 0)
        self._refrescar_lista()
        nota = Fila("Ventanas de administrador", "Windows no deja que Orbit fije ventanas abiertas como "
                                                 "administrador. Al cerrar Orbit se sueltan todas.")
        return [grupo(Fila("Mostrar borde", "Un marco fino del color de acento rodea cada ventana fijada.", borde),
                      titulo="Aspecto"),
                self._lista, grupo(nota, titulo="Cómo funciona")]

    def _refrescar_lista(self):
        if self._lista is None:
            return
        try:
            diseno = self._lista.layout()
            while diseno.count():
                diseno.takeAt(0).widget().deleteLater()
        except RuntimeError:  # la página de ajustes se cerró
            self._lista = None
            return
        filas = []
        for hwnd in self.fijadas:
            soltar = estilo.boton("Soltar")
            soltar.clicked.connect(lambda _=False, h=hwnd: self.soltar(h, avisar=False))
            filas.append(Fila(recortar(ventanas.titulo(hwnd) or "Sin título", 60), ventanas.programa(hwnd), soltar))
        if not filas:
            filas = [Fila("Ninguna ventana fijada", f"Pulsa {self.cfg['atajo']['texto']} con una ventana delante.")]
        diseno.addWidget(grupo(*filas, titulo="Ventanas fijadas"))

    def _borde(self, valor):
        self.guardar(borde=valor)
        for hwnd in self.fijadas:
            actual = self.fijadas[hwnd]
            if valor and actual is None:
                self.fijadas[hwnd] = Borde()
            elif not valor and actual:
                actual.hide()
                actual.deleteLater()
                self.fijadas[hwnd] = None
        self._seguir()
        self._ritmo()
