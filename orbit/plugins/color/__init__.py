"""Plugin Cuentagotas: el atajo abre una lupa, y un clic copia el color de cualquier píxel de la pantalla."""
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QToolTip, QVBoxLayout, QWidget

from ... import estilo
from ...estilo import Segmentado
from ...pantalla import SelectorPantalla
from ...ui import Fila, grupo
from ..base import Plugin
from .formatos import FORMATOS, NOMBRES, a_hex, desde_hex, escribir

MAXIMO_HISTORIAL = 12


class Muestras(QWidget):
    """Fila de muestras redondas: un clic copia ese color."""
    elegida = Signal(str)
    TAM, HUECO = 26, 10

    def __init__(self, describir):
        super().__init__()
        self.colores = []
        self.describir = describir
        self.encima = -1
        self.setMouseTracking(True)
        self.setFixedHeight(self.TAM + 8)
        self.setMinimumWidth(MAXIMO_HISTORIAL * (self.TAM + self.HUECO))

    def fijar(self, colores):
        self.colores = list(colores)
        self.setCursor(Qt.PointingHandCursor if self.colores else Qt.ArrowCursor)
        self.update()

    def _indice(self, pos):
        i = int(pos.x() // (self.TAM + self.HUECO))
        dentro = pos.x() - i * (self.TAM + self.HUECO) <= self.TAM + 4
        return i if 0 <= i < len(self.colores) and dentro else -1

    def mouseMoveEvent(self, evento):
        indice = self._indice(evento.position())
        if indice != self.encima:
            self.encima = indice
            self.update()
            if indice >= 0:
                QToolTip.showText(evento.globalPosition().toPoint(), self.describir(self.colores[indice]), self)
            else:
                QToolTip.hideText()

    def leaveEvent(self, _):
        self.encima = -1
        self.update()

    def mouseReleaseEvent(self, evento):
        indice = self._indice(evento.position())
        if evento.button() == Qt.LeftButton and indice >= 0:
            self.elegida.emit(self.colores[indice])

    def paintEvent(self, _):
        pal = estilo.paleta()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for i, color in enumerate(self.colores):
            centro = QPointF(i * (self.TAM + self.HUECO) + self.TAM / 2 + 2, self.height() / 2)
            if i == self.encima:
                p.setPen(QPen(QColor(pal.acento), 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(centro, self.TAM / 2 + 3, self.TAM / 2 + 3)
            p.setPen(QPen(QColor(255, 255, 255, 60) if pal.oscuro else QColor(0, 0, 0, 40), 1))
            p.setBrush(QColor(color))
            p.drawEllipse(centro, self.TAM / 2, self.TAM / 2)


class PluginColor(Plugin):
    id = "color"
    nombre = "Cuentagotas"
    descripcion = ("Copia el color de cualquier punto de la pantalla en HEX, RGB o HSL, con una lupa para "
                   "acertar al píxel. Guarda los últimos colores.")
    icono = "color"
    texto_atajo = "Elegir un color"

    def __init__(self, app):
        super().__init__(app)
        self.selector = None
        self._muestras = None

    def estado(self):
        return self.estado_atajo()

    @property
    def formato(self):
        formato = self.cfg.get("formato", "hex")
        return formato if formato in FORMATOS else "hex"

    def texto(self, color_hex):
        return escribir(*desde_hex(color_hex), self.formato)

    def al_atajo(self):
        if not self.activo:
            self.avisar_desactivado()
            return
        if self.selector is None:
            self.selector = SelectorPantalla("punto")
            self.selector.describir = lambda c: escribir(c.red(), c.green(), c.blue(), self.formato)
            self.selector.punto.connect(self._elegido)
        self.selector.abrir()

    def detener(self):
        if self.selector:
            self.selector.cerrar()

    def _elegido(self, color):
        self.copiar(a_hex(color.red(), color.green(), color.blue()))

    def copiar(self, color_hex):
        texto = self.texto(color_hex)
        QGuiApplication.clipboard().setText(texto)
        historial = [c for c in self.cfg.get("historial", []) if c != color_hex]
        self.guardar(historial=[color_hex] + historial[:MAXIMO_HISTORIAL - 1])
        self.app.aviso.mostrar(self.icono, f"{texto} copiado", "En el portapapeles", color=color_hex)
        self._refrescar_muestras()

    # --- ajustes
    def grupos_ajustes(self):
        formato = Segmentado(NOMBRES)
        formato.fijar(FORMATOS.index(self.formato))
        formato.cambiado.connect(self._formato)
        self._muestras = Muestras(self.texto)
        self._muestras.elegida.connect(self.copiar)
        borrar = estilo.boton("Borrar")
        borrar.clicked.connect(self._borrar)
        self._fila_historial = Fila("Últimos colores", "", borrar)
        historial = QWidget()  # la fila y sus muestras, en la misma celda
        v = QVBoxLayout(historial)
        v.setContentsMargins(0, 0, 0, 12)
        v.setSpacing(2)
        v.addWidget(self._fila_historial)
        h = QHBoxLayout()
        h.setContentsMargins(12, 0, 14, 0)
        h.addWidget(self._muestras)
        h.addStretch()
        v.addLayout(h)
        self._refrescar_muestras()
        return [grupo(Fila("Formato al copiar", "HEX como #3B82F6, RGB como rgb(59, 130, 246) o HSL como "
                                                "hsl(217, 91%, 60%).", formato), titulo="Copiar"),
                grupo(historial, titulo="Historial"),
                grupo(Fila("Cómo se usa", "Pulsa el atajo, mueve la lupa hasta el color y haz clic. Las flechas "
                                          "mueven el ratón de a un punto; Esc cancela."))]

    def _refrescar_muestras(self):
        if self._muestras is None:
            return
        try:
            historial = self.cfg.get("historial", [])
            self._muestras.fijar(historial)
            self._fila_historial.fijar_detalle("Un clic en una muestra la copia otra vez." if historial else
                                               "Los colores que copies aparecerán aquí.")
        except RuntimeError:  # la página de ajustes se cerró
            self._muestras = None

    def _formato(self, indice):
        self.guardar(formato=FORMATOS[indice])

    def _borrar(self):
        self.guardar(historial=[])
        self._refrescar_muestras()
