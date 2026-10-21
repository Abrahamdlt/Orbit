"""Sistema de diseño de Orbit, inspirado en macOS: colores, tipografía, controles y animaciones."""
import math
from dataclasses import dataclass

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QIcon, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QAbstractButton, QWidget

from . import sistema

FUENTE_TITULOS = "Segoe UI Variable Display"
# Modo bajo consumo (lo fija la app): sin animaciones ni efecto vidrio
BAJO_CONSUMO = False
FUENTE_TEXTO = "Segoe UI Variable Text"


@dataclass(frozen=True)
class Paleta:
    oscuro: bool
    fondo: str
    lateral: str
    superficie: str
    texto: str
    texto2: str
    separador: str
    control: str  # fondo de interruptores apagados y segmentados
    seleccion: str  # pastilla del segmentado / elemento elegido del lateral
    acento: str
    verde: str
    rojo: str
    naranja: str
    vidrio: tuple  # tinte RGBA sobre el fondo desenfocado


CLARA = Paleta(False, "#F5F5F7", "#E9E9EE", "#FFFFFF", "#1D1D1F", "#6E6E73", "rgba(0,0,0,0.08)",
               "#E3E3E8", "#FFFFFF", "#007AFF", "#34C759", "#FF3B30", "#FF9500", (250, 250, 252, 175))
OSCURA = Paleta(True, "#1E1E20", "#28282B", "#2C2C2E", "#F5F5F7", "#98989D", "rgba(255,255,255,0.08)",
                "#3A3A3C", "#636366", "#0A84FF", "#30D158", "#FF453A", "#FF9F0A", (28, 28, 30, 165))


def paleta():
    return OSCURA if sistema.tema_oscuro() else CLARA


def tinte(pal):
    """Color del vidrio. En bajo consumo no hay fondo desenfocado: se usa casi opaco."""
    r, g, b, a = pal.vidrio
    return QColor(r, g, b, 248 if BAJO_CONSUMO else a)


def fuente(tam, peso=QFont.Normal, titulo=False):
    f = QFont(FUENTE_TITULOS if titulo else FUENTE_TEXTO)
    f.setPointSizeF(tam)
    f.setWeight(peso)
    return f


def hoja_de_estilo(p):
    """QSS común para ventanas de Orbit."""
    return f"""
    QWidget {{ color: {p.texto}; font-family: "{FUENTE_TEXTO}"; font-size: 10pt; }}
    QLabel#secundario {{ color: {p.texto2}; }}
    QLabel#titulo {{ font-family: "{FUENTE_TITULOS}"; font-size: 20pt; font-weight: 600; }}
    QLabel#subtitulo {{ font-family: "{FUENTE_TITULOS}"; font-size: 12pt; font-weight: 600; }}
    QLabel#error {{ color: {p.rojo}; }}
    QFrame#grupo {{ background: {p.superficie}; border-radius: 12px; border: 1px solid {p.separador}; }}
    QFrame#linea {{ background: {p.separador}; max-height: 1px; min-height: 1px; border: none; }}
    QPushButton {{ background: {p.control}; color: {p.texto}; border: none; border-radius: 8px;
                   padding: 6px 16px; font-weight: 500; }}
    QPushButton:hover {{ background: {QColor(p.control).darker(108 if not p.oscuro else 85).name()}; }}
    QPushButton:pressed {{ background: {QColor(p.control).darker(116 if not p.oscuro else 75).name()}; }}
    QPushButton[tipo="primario"] {{ background: {p.acento}; color: white; }}
    QPushButton[tipo="primario"]:hover {{ background: {QColor(p.acento).lighter(110).name()}; }}
    QPushButton[tipo="primario"]:disabled {{ background: {p.control}; color: {p.texto2}; }}
    QPushButton[tipo="peligro"] {{ background: transparent; color: {p.rojo}; }}
    QPushButton[tipo="peligro"]:hover {{ background: {p.control}; }}
    QPushButton[tipo="enlace"] {{ background: transparent; color: {p.acento}; padding: 4px 6px; }}
    QCheckBox {{ spacing: 8px; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; }}
    QScrollBar::handle:vertical {{ background: {p.separador}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """


def boton(texto, tipo=None):
    from PySide6.QtWidgets import QPushButton
    b = QPushButton(texto)
    b.setCursor(Qt.PointingHandCursor)
    if tipo:
        b.setProperty("tipo", tipo)
    return b


def resorte(rebote=1.0):
    """Curva con un pequeño rebote al final, como las animaciones de Apple."""
    curva = QEasingCurve(QEasingCurve.OutBack)
    curva.setOvershoot(rebote)
    return curva


def mezclar(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t), round(a.alpha() + (b.alpha() - a.alpha()) * t))


# ---------------------------------------------------------------- vidrio

def desenfocar(imagen, pasos=4):
    """Desenfoque rápido: reducir a la mitad varias veces y volver a ampliar suavizando."""
    tam = imagen.size()
    for _ in range(pasos):
        imagen = imagen.scaled(max(1, imagen.width() // 2), max(1, imagen.height() // 2),
                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    for _ in range(pasos - 1):
        imagen = imagen.scaled(imagen.width() * 2, imagen.height() * 2, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return imagen.scaled(tam, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def capturar_fondo(x, y, ancho, alto):
    """Foto desenfocada de lo que hay en pantalla en ese rectángulo (coordenadas globales)."""
    pantalla = QGuiApplication.screenAt(QPoint(x + ancho // 2, y + alto // 2)) or QGuiApplication.primaryScreen()
    geo = pantalla.geometry()
    captura = pantalla.grabWindow(0, x - geo.x(), y - geo.y(), ancho, alto)
    imagen = desenfocar(captura.toImage())
    imagen.setDevicePixelRatio(captura.devicePixelRatio())
    return QPixmap.fromImage(imagen)


# ---------------------------------------------------------------- logo e iconos

def _squircle(rect):
    camino = QPainterPath()
    radio = rect.width() * 0.235
    camino.addRoundedRect(rect, radio, radio)
    return camino


def dibujar_logo(p, rect):
    """Logo de Orbit: un planeta con un satélite en órbita, sobre un cuadrado redondeado."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    gradiente = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradiente.setColorAt(0, QColor("#7D7AFF"))
    gradiente.setColorAt(1, QColor("#0A84FF"))
    p.fillPath(_squircle(rect), gradiente)
    c, lado = rect.center(), rect.width()
    p.translate(c)
    p.rotate(-28)
    p.setPen(QPen(QColor(255, 255, 255, 235), max(1.2, lado * 0.065)))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(0, 0), lado * 0.36, lado * 0.15)
    p.setPen(Qt.NoPen)
    p.setBrush(Qt.white)
    p.drawEllipse(QPointF(0, 0), lado * 0.15, lado * 0.15)
    angulo = math.radians(-35)
    p.drawEllipse(QPointF(lado * 0.36 * math.cos(angulo), lado * 0.15 * math.sin(angulo)), lado * 0.07, lado * 0.07)
    p.restore()


ICONOS = {
    "radial": ("#FF9F0A", "#FF375F"),
    "fps": ("#30D158", "#30B0C7"),
    "general": ("#A1A1A6", "#6E6E73"),
}


def dibujar_icono(p, rect, tipo):
    """Icono de plugin estilo Ajustes de macOS: cuadrado redondeado de color con un glifo blanco."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    a, b = ICONOS[tipo]
    gradiente = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradiente.setColorAt(0, QColor(a))
    gradiente.setColorAt(1, QColor(b))
    p.fillPath(_squircle(rect), gradiente)
    lado, c = rect.width(), rect.center()
    pluma = QPen(Qt.white, max(1.3, lado * 0.1), Qt.SolidLine, Qt.RoundCap)
    p.setPen(pluma)
    p.setBrush(Qt.NoBrush)
    if tipo == "radial":
        r = lado * 0.27
        caja = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        for i in range(4):
            p.drawArc(caja, int((90 - i * 90 - 12) * 16), int(-66 * 16))
    elif tipo == "fps":
        r = lado * 0.28
        caja = QRectF(c.x() - r, c.y() - r * 0.8, 2 * r, 2 * r)
        p.drawArc(caja, 200 * 16, -220 * 16)
        centro = caja.center()
        p.drawLine(centro, QPointF(centro.x() + r * 0.55, centro.y() - r * 0.5))
    else:
        for i, x in enumerate((0.38, 0.62, 0.45)):
            y = rect.top() + lado * (0.32 + i * 0.18)
            p.setPen(QPen(QColor(255, 255, 255, 200), max(1, lado * 0.06), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(rect.left() + lado * 0.24, y), QPointF(rect.right() - lado * 0.24, y))
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.white)
            p.drawEllipse(QPointF(rect.left() + lado * x, y), lado * 0.075, lado * 0.075)
            p.setBrush(Qt.NoBrush)
    p.restore()


def pixmap_logo(tam):
    pixmap = QPixmap(tam, tam)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    dibujar_logo(p, QRectF(tam * 0.04, tam * 0.04, tam * 0.92, tam * 0.92))
    p.end()
    return pixmap


def icono_orbit():
    icono = QIcon()
    for tam in (16, 20, 24, 32, 48, 64, 128, 256):
        icono.addPixmap(pixmap_logo(tam))
    return icono


class IconoPlugin(QWidget):
    def __init__(self, tipo, tam=28, parent=None):
        super().__init__(parent)
        self.tipo = tipo
        self.setFixedSize(tam, tam)

    def paintEvent(self, _):
        p = QPainter(self)
        dibujar_icono(p, QRectF(self.rect()), self.tipo)


# ---------------------------------------------------------------- controles

class Interruptor(QAbstractButton):
    """Interruptor tipo iOS con animación de resorte."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 25)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=260, easingCurve=resorte(1.1))
        self._anim.valueChanged.connect(self._mover)
        self.toggled.connect(self._animar)

    def _mover(self, valor):
        self._pos = valor
        self.update()

    def _animar(self, activo):
        self._anim.stop()
        if BAJO_CONSUMO:
            self._mover(1.0 if activo else 0.0)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if activo else 0.0)
        self._anim.start()

    def fijar(self, activo):
        """Cambia el estado sin animar ni emitir señales."""
        self.blockSignals(True)
        self.setChecked(activo)
        self.blockSignals(False)
        self._anim.stop()
        self._pos = 1.0 if activo else 0.0
        self.update()

    def paintEvent(self, _):
        pal = paleta()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = max(0.0, min(1.0, self._pos))
        p.setPen(Qt.NoPen)
        fondo = mezclar(pal.control, pal.verde, t)
        if not self.isEnabled():
            fondo.setAlpha(110)
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), self.height() / 2, self.height() / 2)
        d = self.height() - 4
        x = 2 + (self.width() - d - 4) * self._pos
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, 2.8, d, d))
        p.setBrush(Qt.white)
        p.drawEllipse(QRectF(x, 2, d, d))


class Segmentado(QWidget):
    """Control segmentado de macOS: una pastilla que se desliza a la opción elegida."""
    cambiado = Signal(int)

    def __init__(self, opciones, parent=None):
        super().__init__(parent)
        self.opciones = opciones
        self.indice = 0
        self._x = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.setMinimumWidth(70 * len(opciones))
        self._anim = QVariantAnimation(self, duration=240, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._mover)

    def _mover(self, valor):
        self._x = valor
        self.update()

    def fijar(self, indice):
        self.indice = indice
        self._x = float(indice)
        self.update()

    def mousePressEvent(self, evento):
        indice = min(len(self.opciones) - 1, int(evento.position().x() / (self.width() / len(self.opciones))))
        if indice != self.indice:
            self.indice = indice
            self._anim.stop()
            if BAJO_CONSUMO:
                self._mover(float(indice))
            else:
                self._anim.setStartValue(self._x)
                self._anim.setEndValue(float(indice))
                self._anim.start()
            self.cambiado.emit(indice)

    def paintEvent(self, _):
        pal = paleta()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(pal.control))
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        ancho = self.width() / len(self.opciones)
        pastilla = QRectF(self._x * ancho + 2, 2, ancho - 4, self.height() - 4)
        p.setBrush(QColor(0, 0, 0, 25))
        p.drawRoundedRect(pastilla.translated(0, 0.8), 6, 6)
        p.setBrush(QColor(pal.seleccion))
        p.drawRoundedRect(pastilla, 6, 6)
        p.setFont(fuente(9, QFont.Medium))
        for i, texto in enumerate(self.opciones):
            p.setPen(QColor(pal.texto if i == self.indice else pal.texto2))
            p.drawText(QRectF(i * ancho, 0, ancho, self.height()), Qt.AlignCenter, texto)


class Cargando(QWidget):
    """Rueda de carga de macOS (12 rayitas que se van apagando)."""

    def __init__(self, tam=22, parent=None):
        super().__init__(parent)
        self.setFixedSize(tam, tam)
        self._paso = 0
        self._reloj = QTimer(self, interval=80)
        self._reloj.timeout.connect(self._avanzar)
        self._reloj.start()

    def _avanzar(self):
        self._paso = (self._paso + 1) % 12
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        color = QColor(paleta().texto2)
        lado = self.width()
        for i in range(12):
            color.setAlphaF(0.15 + 0.85 * (((i - self._paso) % 12) / 11))
            p.setPen(QPen(color, lado * 0.09, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(0, -lado * 0.25), QPointF(0, -lado * 0.45))
            p.rotate(30)


# ---------------------------------------------------------------- aviso flotante (HUD)

class Aviso(QWidget):
    """Cartel pequeño abajo en el centro, como el de volumen de macOS. No usa notificaciones de Windows."""

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.tipo, self.titulo, self.detalle = "general", "", ""
        self._t = 0.0
        self._anim = QVariantAnimation(self, duration=260, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._mover)
        self._anim.finished.connect(lambda: self._t <= 0.01 and self.hide())
        self._espera = QTimer(self, singleShot=True, interval=1500)
        self._espera.timeout.connect(lambda: self._ir_a(0.0))

    def _mover(self, valor):
        self._t = valor
        self.setWindowOpacity(max(0.0, min(1.0, valor)))
        self.update()

    def _ir_a(self, destino):
        self._anim.stop()
        if BAJO_CONSUMO:
            self._mover(destino)
            if destino <= 0:
                self.hide()
            return
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(destino)
        self._anim.start()

    def mostrar(self, tipo, titulo, detalle=""):
        self.tipo, self.titulo, self.detalle = tipo, titulo, detalle
        ancho = max(220, 90 + 9 * max(len(titulo), len(detalle)))
        self.resize(ancho, 64)
        zona = QGuiApplication.primaryScreen().availableGeometry()
        self.move(zona.center().x() - ancho // 2, zona.bottom() - 140)
        self.show()
        sistema.siempre_encima(int(self.winId()))
        self._ir_a(1.0)
        self._espera.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        escala = 0.92 + 0.08 * self._t
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(escala, escala)
        p.translate(-self.width() / 2, -self.height() / 2)
        caja = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(30, 30, 32, 225))
        p.drawRoundedRect(caja, 18, 18)
        dibujar_icono(p, QRectF(16, 16, 32, 32), self.tipo)
        p.setPen(Qt.white)
        p.setFont(fuente(10.5, QFont.DemiBold))
        p.drawText(QRectF(60, 12, self.width() - 72, 22), Qt.AlignLeft | Qt.AlignVCenter, self.titulo)
        p.setPen(QColor(255, 255, 255, 160))
        p.setFont(fuente(9))
        p.drawText(QRectF(60, 32, self.width() - 72, 20), Qt.AlignLeft | Qt.AlignVCenter, self.detalle)


def animar_aparicion(ventana, desplazamiento=10, duracion=240):
    """Entrada suave: aparece desde un poco más abajo y se desvanece hacia visible."""
    if BAJO_CONSUMO:
        ventana.setWindowOpacity(1.0)
        ventana.show()
        return
    destino = ventana.pos()
    ventana.setWindowOpacity(0.0)
    ventana.move(destino.x(), destino.y() + desplazamiento)
    ventana.show()
    opacidad = QPropertyAnimation(ventana, b"windowOpacity", ventana, duration=duracion,
                                  startValue=0.0, endValue=1.0, easingCurve=QEasingCurve.OutCubic)
    posicion = QPropertyAnimation(ventana, b"pos", ventana, duration=duracion + 60,
                                  startValue=ventana.pos(), endValue=destino, easingCurve=resorte(0.8))
    opacidad.start(QPropertyAnimation.DeleteWhenStopped)
    posicion.start(QPropertyAnimation.DeleteWhenStopped)
