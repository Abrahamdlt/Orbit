"""Panel que se abre al hacer clic en el icono de la bandeja, al estilo del Centro de control de macOS."""
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from . import VERSION, estilo
from .estilo import IconoPlugin, Interruptor

SOMBRA = 14  # margen transparente alrededor para la sombra
RADIO = 16
ALTO_MAXIMO = 0.8  # fracción del alto de la pantalla: si hay más plugins, la lista se desplaza


class Recortada(QLabel):
    """Una línea que termina en «…» si no cabe, en vez de ensanchar la fila (y cortar el interruptor).
    El texto entero se ve al pasar el ratón."""

    def __init__(self, texto=""):
        super().__init__()
        self.completo = texto
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._recortar()

    def fijar(self, texto):
        self.completo = texto
        self._recortar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._recortar()

    def _recortar(self):
        visible = self.fontMetrics().elidedText(self.completo, Qt.ElideRight, max(0, self.width()))
        self.setText(visible)
        self.setToolTip(self.completo if visible != self.completo else "")


class FilaPlugin(QWidget):
    def __init__(self, panel, plugin):
        super().__init__()
        self.panel, self.plugin = panel, plugin
        self.encima = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)
        diseno = QHBoxLayout(self)
        diseno.setContentsMargins(10, 6, 10, 6)
        diseno.setSpacing(11)
        diseno.addWidget(IconoPlugin(plugin.icono, 32))
        textos = QVBoxLayout()
        textos.setSpacing(0)
        nombre = Recortada(plugin.nombre)
        nombre.setFont(estilo.fuente(10.5, QFont.DemiBold))
        self.estado = Recortada()
        self.estado.setObjectName("secundario")
        self.estado.setFont(estilo.fuente(8.5))
        textos.addStretch()
        textos.addWidget(nombre)
        textos.addWidget(self.estado)
        textos.addStretch()
        diseno.addLayout(textos, 1)
        self.interruptor = Interruptor()
        self.interruptor.toggled.connect(lambda v: panel.app.fijar_activo(plugin, v))
        self.anadir = estilo.boton("Añadir", "primario")
        self.anadir.clicked.connect(lambda: panel.app.instalar_plugin(plugin))
        diseno.addWidget(self.interruptor)
        diseno.addWidget(self.anadir)

    def refrescar(self):
        instalado = self.plugin.instalado
        self.interruptor.setVisible(instalado)
        self.anadir.setVisible(not instalado)
        self.interruptor.fijar(self.plugin.activo)
        self.estado.fijar(self.plugin.estado() if instalado else "No instalado")

    def enterEvent(self, _):
        self.encima = True
        self.update()

    def leaveEvent(self, _):
        self.encima = False
        self.update()

    def mouseReleaseEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self.panel.hide()
            self.panel.app.abrir_ajustes(self.plugin.id)

    def paintEvent(self, _):
        if self.encima:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            color = QColor(self.panel.paleta.texto)
            color.setAlpha(18)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 0, -2, 0), 10, 10)


class Panel(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.paleta = estilo.paleta()
        self.fondo = None
        self.oculto_en = 0.0
        self.setFixedWidth(330 + 2 * SOMBRA)

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(SOMBRA + 10, SOMBRA + 12, SOMBRA + 10, SOMBRA + 10)
        diseno.setSpacing(2)

        cabecera = QHBoxLayout()
        cabecera.setContentsMargins(6, 0, 6, 6)
        logo = QLabel()
        logo.setPixmap(estilo.pixmap_logo(44))
        logo.setFixedSize(22, 22)
        logo.setScaledContents(True)
        titulo = QLabel("Orbit")
        titulo.setFont(estilo.fuente(12.5, QFont.DemiBold, titulo=True))
        version = QLabel(f"v{VERSION}")
        version.setObjectName("secundario")
        version.setFont(estilo.fuente(8.5))
        cabecera.addWidget(logo)
        cabecera.addSpacing(4)
        cabecera.addWidget(titulo)
        cabecera.addStretch()
        cabecera.addWidget(version)
        diseno.addLayout(cabecera)

        seccion = QLabel("PLUGINS")
        seccion.setObjectName("secundario")
        seccion.setFont(estilo.fuente(7.5, QFont.DemiBold))
        seccion.setContentsMargins(8, 4, 0, 2)
        diseno.addWidget(seccion)
        self.lista = QWidget()
        filas = QVBoxLayout(self.lista)
        filas.setContentsMargins(0, 0, 0, 0)
        filas.setSpacing(2)
        self.filas = [FilaPlugin(self, plugin) for plugin in app.plugins]
        for fila in self.filas:
            filas.addWidget(fila)
        self.desplazable = QScrollArea()
        self.desplazable.setWidgetResizable(True)
        self.desplazable.setFrameShape(QScrollArea.NoFrame)
        self.desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.desplazable.setWidget(self.lista)
        diseno.addWidget(self.desplazable)

        diseno.addSpacing(6)
        pie = QHBoxLayout()
        pie.setContentsMargins(4, 6, 4, 0)
        ajustes = estilo.boton("Ajustes de Orbit…", "enlace")
        ajustes.clicked.connect(lambda: (self.hide(), app.abrir_ajustes()))
        salir = estilo.boton("Salir", "enlace")
        salir.clicked.connect(app.salir)
        pie.addWidget(ajustes)
        pie.addStretch()
        pie.addWidget(salir)
        diseno.addLayout(pie)
        self._estilo()

    def _estilo(self):
        p = self.paleta
        self.setStyleSheet(estilo.hoja_de_estilo(p) + f"QPushButton[tipo=\"enlace\"] {{ color: {p.texto}; }}"
                           f"QPushButton[tipo=\"enlace\"]:hover {{ color: {p.acento}; }}")

    def refrescar(self):
        for fila in self.filas:
            fila.refrescar()

    def alternar(self, zona_icono):
        # Un clic en el icono con el panel abierto lo cierra (Qt ya lo ocultó al hacer clic fuera)
        if self.isVisible() or time.monotonic() - self.oculto_en < 0.3:
            self.hide()
            return
        paleta = estilo.paleta()
        if paleta != self.paleta:
            self.paleta = paleta
            self._estilo()
        pantalla = QGuiApplication.screenAt(zona_icono.center()) or QGuiApplication.primaryScreen()
        zona = pantalla.availableGeometry()
        self.refrescar()
        self._ajustar_alto(zona)
        x = min(max(zona.left(), zona_icono.center().x() - self.width() // 2), zona.right() - self.width() + SOMBRA - 4)
        y = zona.bottom() - self.height() + SOMBRA - 4 if zona_icono.top() >= zona.bottom() - 4 else zona.top() - SOMBRA + 4
        self.fondo = None
        if not estilo.BAJO_CONSUMO:
            try:
                self.fondo = estilo.capturar_fondo(x, y, self.width(), self.height())
            except Exception:
                pass
        self.move(x, y)
        estilo.animar_aparicion(self, desplazamiento=12)
        self.activateWindow()

    def _ajustar_alto(self, zona):
        completo = self.lista.sizeHint().height()
        self.desplazable.setFixedHeight(completo)
        self.adjustSize()
        sobra = self.height() - 2 * SOMBRA - int(zona.height() * ALTO_MAXIMO)
        if sobra > 0:
            self.desplazable.setFixedHeight(completo - sobra)
            self.adjustSize()

    def hideEvent(self, evento):
        self.oculto_en = time.monotonic()
        super().hideEvent(evento)

    def paintEvent(self, _):
        estilo.pintar_vidrio(QPainter(self), self.rect(), SOMBRA, RADIO, self.fondo, self.paleta)
