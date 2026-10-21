"""Sistema de diseño de Orbit, inspirado en macOS: colores, tipografía, controles y animaciones."""
import math
from dataclasses import dataclass

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QIcon, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF)
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
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
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


def pintar_vidrio(p, rect, sombra, radio, fondo, pal):
    """Tarjeta de vidrio con sombra difusa (panel de la bandeja, historial del portapapeles).
    rect es la ventana entera; la tarjeta queda dentro, a `sombra` puntos del borde."""
    p.setRenderHint(QPainter.Antialiasing)
    caja = QRectF(rect).adjusted(sombra, sombra, -sombra, -sombra)
    for i in range(sombra, 0, -2):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, int(5 * (1 - i / sombra) ** 1.5 * (3 if pal.oscuro else 2))))
        p.drawRoundedRect(caja.adjusted(-i, -i + 4, i, i + 4), radio + i, radio + i)
    forma = QPainterPath()
    forma.addRoundedRect(caja, radio, radio)
    p.save()
    p.setClipPath(forma)
    if fondo is not None:
        p.drawPixmap(0, 0, fondo)
    p.fillPath(forma, tinte(pal))
    brillo = QLinearGradient(caja.topLeft(), caja.bottomLeft())
    brillo.setColorAt(0, QColor(255, 255, 255, 30 if pal.oscuro else 60))
    brillo.setColorAt(0.4, QColor(255, 255, 255, 0))
    p.fillPath(forma, brillo)
    p.restore()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 40 if pal.oscuro else 160), 1))
    p.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), radio, radio)
    p.setPen(QPen(QColor(0, 0, 0, 90 if pal.oscuro else 35), 1))
    p.drawRoundedRect(caja.adjusted(-0.5, -0.5, 0.5, 0.5), radio + 0.5, radio + 0.5)


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
    "ocr": ("#0A84FF", "#5E5CE6"),
    "portapapeles": ("#8E9BB0", "#636B78"),
    "audio": ("#FF6482", "#FF3B30"),
    "encima": ("#FFD60A", "#FF9F0A"),
    "despierto": ("#B48A60", "#F2902A"),
    "color": ("#BF5AF2", "#FF375F"),
    "pomodoro": ("#FF453A", "#FF9F0A"),
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
    fina = QPen(Qt.white, max(1.0, lado * 0.07), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pluma)
    p.setBrush(Qt.NoBrush)

    def pt(x, y):  # punto en fracciones del icono
        return QPointF(rect.left() + lado * x, rect.top() + lado * y)

    def marco(x1, y1, x2, y2):
        return QRectF(pt(x1, y1), pt(x2, y2))

    def relleno():
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.white)

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
    elif tipo == "ocr":  # una «T» dentro de las esquinas de un marco
        p.setPen(fina)
        for x, y, dx, dy in ((0.22, 0.22, 1, 1), (0.78, 0.22, -1, 1), (0.22, 0.78, 1, -1), (0.78, 0.78, -1, -1)):
            p.drawPolyline([pt(x + 0.15 * dx, y), pt(x, y), pt(x, y + 0.15 * dy)])
        p.setPen(pluma)
        p.drawLine(pt(0.36, 0.37), pt(0.64, 0.37))
        p.drawLine(pt(0.5, 0.37), pt(0.5, 0.64))
    elif tipo == "portapapeles":
        p.setPen(fina)
        p.drawRoundedRect(marco(0.27, 0.24, 0.73, 0.8), lado * 0.07, lado * 0.07)
        p.drawLine(pt(0.37, 0.47), pt(0.63, 0.47))
        p.drawLine(pt(0.37, 0.61), pt(0.56, 0.61))
        relleno()
        p.drawRoundedRect(marco(0.38, 0.17, 0.62, 0.3), lado * 0.04, lado * 0.04)
    elif tipo == "audio":  # audífonos
        p.setPen(QPen(Qt.white, max(1.0, lado * 0.075), Qt.SolidLine, Qt.FlatCap))
        p.drawArc(marco(0.25, 0.24, 0.75, 0.74), 0, 180 * 16)
        relleno()
        p.drawRoundedRect(marco(0.19, 0.48, 0.34, 0.76), lado * 0.05, lado * 0.05)
        p.drawRoundedRect(marco(0.66, 0.48, 0.81, 0.76), lado * 0.05, lado * 0.05)
    elif tipo == "encima":
        dibujar_chincheta(p, rect, QColor(Qt.white))
    elif tipo == "despierto":  # taza de café
        p.setPen(fina)
        p.drawArc(marco(0.55, 0.47, 0.77, 0.67), -90 * 16, 180 * 16)
        for x in (0.38, 0.52):
            vapor = QPainterPath(pt(x, 0.36))
            vapor.cubicTo(pt(x - 0.05, 0.31), pt(x + 0.05, 0.27), pt(x, 0.21))
            p.drawPath(vapor)
        relleno()
        taza = QPainterPath()
        taza.addRoundedRect(marco(0.24, 0.42, 0.66, 0.78), lado * 0.11, lado * 0.11)
        borde = QPainterPath()
        borde.addRect(marco(0.24, 0.42, 0.66, 0.55))
        p.drawPath(taza.united(borde))
    elif tipo == "color":  # cuentagotas inclinado
        p.translate(c)
        p.rotate(45)
        p.translate(-c)
        relleno()
        p.drawRoundedRect(marco(0.41, 0.12, 0.59, 0.33), lado * 0.08, lado * 0.08)
        p.drawRoundedRect(marco(0.34, 0.32, 0.66, 0.39), lado * 0.03, lado * 0.03)
        p.drawRect(marco(0.455, 0.39, 0.545, 0.72))
        p.drawPolygon(QPolygonF([pt(0.455, 0.72), pt(0.545, 0.72), pt(0.5, 0.86)]))
    elif tipo == "pomodoro":  # reloj con el tiempo restante como un arco
        p.setPen(fina)
        p.drawEllipse(pt(0.5, 0.55), lado * 0.29, lado * 0.29)
        p.drawLine(pt(0.5, 0.15), pt(0.5, 0.2))
        p.drawLine(pt(0.43, 0.15), pt(0.57, 0.15))
        relleno()
        p.drawPie(marco(0.28, 0.33, 0.72, 0.77), 90 * 16, -130 * 16)
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


def dibujar_chincheta(p, rect, color):
    """Chincheta inclinada (icono de Siempre encima y elementos fijados del portapapeles)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    lado, c = rect.width(), rect.center()

    def pt(x, y):
        return QPointF(rect.left() + lado * x, rect.top() + lado * y)

    p.translate(c)
    p.rotate(40)
    p.translate(-c)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(pt(0.37, 0.17), pt(0.63, 0.26)), lado * 0.03, lado * 0.03)
    p.drawPolygon(QPolygonF([pt(0.42, 0.26), pt(0.58, 0.26), pt(0.6, 0.46), pt(0.4, 0.46)]))
    p.drawRoundedRect(QRectF(pt(0.31, 0.45), pt(0.69, 0.53)), lado * 0.035, lado * 0.035)
    p.setPen(QPen(color, max(1.0, lado * 0.07), Qt.SolidLine, Qt.RoundCap))
    p.drawLine(pt(0.5, 0.53), pt(0.5, 0.82))
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
        self.tipo, self.titulo, self.detalle, self.color = "general", "", "", None
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

    def mostrar(self, tipo, titulo, detalle="", color=None):
        """color: en lugar del icono se ve una muestra redonda de ese color (lo usa el Cuentagotas)."""
        self.tipo, self.titulo, self.detalle = tipo, titulo, detalle
        self.color = QColor(color) if color else None
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
        if self.color is not None:
            p.setPen(QPen(QColor(255, 255, 255, 110), 1.5))
            p.setBrush(self.color)
            p.drawEllipse(QRectF(17, 17, 30, 30))
        else:
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
