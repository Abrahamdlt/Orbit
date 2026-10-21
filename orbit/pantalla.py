"""Selector de pantalla: congela lo que se ve en todos los monitores para elegir un área o un punto.

Modo "area": arrastrar un rectángulo sobre la captura oscurecida (lo usa Texto de pantalla).
Modo "punto": una lupa sigue al ratón y un clic elige el color de ese píxel (lo usa el Cuentagotas).
Esc o el botón derecho cancelan. Hay una ventana por monitor, así cada una usa su propia escala.
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import estilo
from .sistema import user32

VK_ESCAPE = 0x1B
PIXELES_LUPA, AUMENTO = 11, 10  # la lupa muestra 11×11 píxeles, cada uno de 10×10
LADO_LUPA = PIXELES_LUPA * AUMENTO
OSCURO = QColor(0, 0, 0, 110)
AYUDA = {"area": "Arrastra para elegir un área  ·  Esc para cancelar",
         "punto": "Haz clic para copiar el color  ·  Esc para cancelar"}


class SelectorPantalla(QObject):
    area = Signal(QImage)   # el recorte, en píxeles reales
    punto = Signal(QColor)
    cancelado = Signal()

    def __init__(self, modo):
        super().__init__()
        self.modo = modo
        self.ayuda = AYUDA[modo]
        self.describir = lambda color: color.name().upper()  # texto bajo la lupa
        self.lienzos = []
        self._esc = QTimer(self, interval=50)  # Esc aunque Windows no nos dé el foco del teclado
        self._esc.timeout.connect(lambda: user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000 and self.cancelar())

    @property
    def abierto(self):
        return bool(self.lienzos)

    def abrir(self):
        if self.lienzos:
            return
        # Primero todas las capturas, después las ventanas: si no, saldrían en las fotos
        capturas = [(pantalla, pantalla.grabWindow(0)) for pantalla in QGuiApplication.screens()]
        for pantalla, captura in capturas:
            lienzo = _Lienzo(self, pantalla, captura)
            self.lienzos.append(lienzo)
            lienzo.show()
        bajo_raton = QGuiApplication.screenAt(QCursor.pos())
        for lienzo in self.lienzos:
            if lienzo.pantalla is bajo_raton:
                lienzo.raise_()
                lienzo.activateWindow()
                lienzo.setFocus()
        self._esc.start()

    def cerrar(self):
        self._esc.stop()
        for lienzo in self.lienzos:
            lienzo.hide()
            lienzo.deleteLater()
        self.lienzos = []  # las capturas se liberan con las ventanas

    def cancelar(self):
        if self.lienzos:
            self.cerrar()
            self.cancelado.emit()

    def _elegir_area(self, imagen):
        self.cerrar()
        self.area.emit(imagen)

    def _elegir_punto(self, color):
        self.cerrar()
        self.punto.emit(color)


class _Lienzo(QWidget):
    def __init__(self, selector, pantalla, captura):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.selector, self.pantalla, self.captura = selector, pantalla, captura
        self.escala = captura.devicePixelRatio()
        self.imagen = captura.toImage() if selector.modo == "punto" else None
        self.inicio = self.fin = None   # rectángulo que se arrastra (coordenadas de la ventana)
        self.raton = None               # punto: píxel real bajo el ratón
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor if selector.modo == "area" else Qt.BlankCursor)
        self.setScreen(pantalla)
        self.setGeometry(pantalla.geometry())
        if selector.modo == "area":
            # Versión oscurecida hecha una vez: así dibujar al arrastrar es barato
            self.oscura = captura.copy()
            p = QPainter(self.oscura)
            p.fillRect(self.oscura.rect(), OSCURO)
            p.end()
        if selector.modo == "punto":
            self._seguir_raton()

    # --- área
    def _seleccion(self):
        if self.inicio is None or self.fin is None:
            return QRectF()
        return QRectF(self.inicio, self.fin).normalized()

    def _zona_seleccion(self):
        return self._seleccion().toAlignedRect().adjusted(-4, -4, 4, 40)

    # --- punto: el ratón se lee en píxeles reales, para elegir exactamente el que está debajo
    def _seguir_raton(self):
        cursor = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(cursor))
        origen = self.pantalla.geometry().topLeft()  # Qt guarda el origen de cada monitor en píxeles reales
        real = QPoint(cursor.x - origen.x(), cursor.y - origen.y())
        if not QRect(QPoint(0, 0), self.captura.size()).contains(real):
            real = None
        if real != self.raton:
            antes = self._zona_lupa()
            self.raton = real
            self.update(antes.united(self._zona_lupa()))

    def _centro_lupa(self):
        return QPointF((self.raton.x() + 0.5) / self.escala, (self.raton.y() + 0.5) / self.escala)

    def _zona_lupa(self):
        if self.raton is None:
            return QRect()
        c = self._centro_lupa()
        return QRectF(c.x() - LADO_LUPA / 2 - 8, c.y() - LADO_LUPA / 2 - 8, LADO_LUPA + 16,
                      LADO_LUPA + 60).toAlignedRect().adjusted(-40, 0, 40, 0)

    def color(self):
        return self.imagen.pixelColor(self.raton) if self.raton is not None else None

    # --- eventos
    def mousePressEvent(self, evento):
        if evento.button() == Qt.RightButton:
            self.selector.cancelar()
        elif evento.button() == Qt.LeftButton:
            if self.selector.modo == "punto":
                self._seguir_raton()
                if self.raton is not None:
                    self.selector._elegir_punto(self.color())
            else:
                self.inicio = self.fin = evento.position()
                self.update()

    def mouseMoveEvent(self, evento):
        if self.selector.modo == "punto":
            self._seguir_raton()
        elif self.inicio is not None:
            antes = self._zona_seleccion()
            self.fin = evento.position()
            self.update(antes.united(self._zona_seleccion()))

    def leaveEvent(self, _):
        if self.selector.modo == "punto":  # el ratón pasó a otro monitor: aquí se borra la lupa
            self._seguir_raton()

    def mouseReleaseEvent(self, evento):
        if self.selector.modo != "area" or evento.button() != Qt.LeftButton or self.inicio is None:
            return
        seleccion = self._seleccion()
        self.inicio = self.fin = None
        self.update()
        if seleccion.width() < 4 or seleccion.height() < 4:  # un clic suelto: se sigue eligiendo
            return
        real = QRect(round(seleccion.x() * self.escala), round(seleccion.y() * self.escala),
                     round(seleccion.width() * self.escala), round(seleccion.height() * self.escala))
        self.selector._elegir_area(self.captura.copy(real).toImage())

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.selector.cancelar()
        elif self.selector.modo == "punto" and evento.key() in (Qt.Key_Return, Qt.Key_Enter) and self.raton:
            self.selector._elegir_punto(self.color())
        elif self.selector.modo == "punto":  # flechas: mover el ratón de a un punto, para afinar
            paso = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
            if evento.key() in paso:
                dx, dy = paso[evento.key()]
                QCursor.setPos(QCursor.pos() + QPoint(dx, dy))
                self._seguir_raton()

    # --- dibujo
    def paintEvent(self, evento):
        p = QPainter(self)
        if self.selector.modo == "area":
            p.drawPixmap(0, 0, self.oscura)
            seleccion = self._seleccion()
            if not seleccion.isEmpty():
                real = QRectF(seleccion.x() * self.escala, seleccion.y() * self.escala,
                              seleccion.width() * self.escala, seleccion.height() * self.escala)
                p.drawPixmap(seleccion, self.captura, real)
                self._pintar_marco(p, seleccion)
        else:
            p.drawPixmap(0, 0, self.captura)
            self._pintar_lupa(p)
        if evento.rect().intersects(self._zona_ayuda()):
            self._pintar_ayuda(p)

    def _zona_ayuda(self):
        return QRect(self.width() // 2 - 220, 22, 440, 34)

    def _pintar_ayuda(self, p):
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(estilo.fuente(9.5, QFont.Medium))
        ancho = p.fontMetrics().horizontalAdvance(self.selector.ayuda) + 36
        caja = QRectF(self.width() / 2 - ancho / 2, 22, ancho, 34)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(30, 30, 32, 225))
        p.drawRoundedRect(caja, 17, 17)
        p.setPen(QColor(255, 255, 255, 230))
        p.drawText(caja, Qt.AlignCenter, self.selector.ayuda)

    def _pintar_marco(self, p, seleccion):
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(estilo.paleta().acento), 1.5))
        p.drawRect(seleccion.adjusted(-0.75, -0.75, 0.75, 0.75))
        texto = f"{round(seleccion.width() * self.escala)} × {round(seleccion.height() * self.escala)}"
        p.setFont(estilo.fuente(8.5, QFont.DemiBold))
        ancho = p.fontMetrics().horizontalAdvance(texto) + 16
        etiqueta = QRectF(seleccion.center().x() - ancho / 2, seleccion.bottom() + 8, ancho, 22)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(30, 30, 32, 225))
        p.drawRoundedRect(etiqueta, 11, 11)
        p.setPen(Qt.white)
        p.drawText(etiqueta, Qt.AlignCenter, texto)

    def _pintar_lupa(self, p):
        if self.raton is None:
            return
        p.setRenderHint(QPainter.Antialiasing)
        c = self._centro_lupa()
        caja = QRectF(c.x() - LADO_LUPA / 2, c.y() - LADO_LUPA / 2, LADO_LUPA, LADO_LUPA)
        circulo = QPainterPath()
        circulo.addEllipse(caja)
        p.save()
        p.setClipPath(circulo)
        p.fillRect(caja, QColor(40, 40, 42))
        mitad = PIXELES_LUPA // 2
        origen = QRectF(self.raton.x() - mitad, self.raton.y() - mitad, PIXELES_LUPA, PIXELES_LUPA)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)  # píxeles nítidos, sin suavizar
        p.drawImage(caja, self.imagen, origen)
        p.setPen(QPen(QColor(0, 0, 0, 35), 1))
        for i in range(1, PIXELES_LUPA):
            p.drawLine(QPointF(caja.left() + i * AUMENTO, caja.top()), QPointF(caja.left() + i * AUMENTO, caja.bottom()))
            p.drawLine(QPointF(caja.left(), caja.top() + i * AUMENTO), QPointF(caja.right(), caja.top() + i * AUMENTO))
        centro = QRectF(caja.left() + mitad * AUMENTO, caja.top() + mitad * AUMENTO, AUMENTO, AUMENTO)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 160), 3))
        p.drawRect(centro)
        p.setPen(QPen(Qt.white, 1.5))
        p.drawRect(centro)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 235), 3))
        p.drawEllipse(caja)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.drawEllipse(caja.adjusted(-2, -2, 2, 2))

        color = self.color()
        texto = self.selector.describir(color)
        p.setFont(estilo.fuente(9, QFont.DemiBold))
        ancho = p.fontMetrics().horizontalAdvance(texto) + 44
        etiqueta = QRectF(c.x() - ancho / 2, caja.bottom() + 10, ancho, 26)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(30, 30, 32, 230))
        p.drawRoundedRect(etiqueta, 13, 13)
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.setBrush(color)
        p.drawEllipse(QRectF(etiqueta.left() + 9, etiqueta.top() + 7, 12, 12))
        p.setPen(Qt.white)
        p.drawText(etiqueta.adjusted(28, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, texto)
