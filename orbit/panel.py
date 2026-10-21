"""Panel que se abre al hacer clic en el icono de la bandeja, al estilo del Centro de control de macOS."""
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import VERSION, estilo
from .estilo import IconoPlugin, Interruptor

SOMBRA = 14  # margen transparente alrededor para la sombra
RADIO = 16


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
        nombre = QLabel(plugin.nombre)
        nombre.setFont(estilo.fuente(10.5, QFont.DemiBold))
        self.estado = QLabel()
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
        self.refrescar()

    def refrescar(self):
        instalado = self.plugin.instalado
        self.interruptor.setVisible(instalado)
        self.anadir.setVisible(not instalado)
        self.interruptor.fijar(self.plugin.activo)
        self.estado.setText(self.plugin.estado() if instalado else
                            "No instalado")

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
        self.filas = [FilaPlugin(self, plugin) for plugin in app.plugins]
        for fila in self.filas:
            diseno.addWidget(fila)

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
        self.refrescar()
        self.adjustSize()
        pantalla = QGuiApplication.screenAt(zona_icono.center()) or QGuiApplication.primaryScreen()
        zona = pantalla.availableGeometry()
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

    def hideEvent(self, evento):
        self.oculto_en = time.monotonic()
        super().hideEvent(evento)

    def paintEvent(self, _):
        pal = self.paleta
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        caja = QRectF(self.rect()).adjusted(SOMBRA, SOMBRA, -SOMBRA, -SOMBRA)
        for i in range(SOMBRA, 0, -2):  # sombra difusa
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, int(5 * (1 - i / SOMBRA) ** 1.5 * (3 if pal.oscuro else 2))))
            p.drawRoundedRect(caja.adjusted(-i, -i + 4, i, i + 4), RADIO + i, RADIO + i)
        forma = QPainterPath()
        forma.addRoundedRect(caja, RADIO, RADIO)
        p.save()
        p.setClipPath(forma)
        if self.fondo is not None:
            p.drawPixmap(0, 0, self.fondo)
        p.fillPath(forma, estilo.tinte(pal))
        brillo = QLinearGradient(caja.topLeft(), caja.bottomLeft())
        brillo.setColorAt(0, QColor(255, 255, 255, 30 if pal.oscuro else 60))
        brillo.setColorAt(0.4, QColor(255, 255, 255, 0))
        p.fillPath(forma, brillo)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 40 if pal.oscuro else 160), 1))
        p.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), RADIO, RADIO)
        p.setPen(QPen(QColor(0, 0, 0, 90 if pal.oscuro else 35), 1))
        p.drawRoundedRect(caja.adjusted(-0.5, -0.5, 0.5, 0.5), RADIO + 0.5, RADIO + 0.5)
