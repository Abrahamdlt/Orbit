"""Pastilla flotante: una cápsula oscura y discreta en una esquina, encima de todas las ventanas y sin recibir clics.

La usan el Medidor FPS y el Pomodoro. Cada una dibuja su contenido con ancho_contenido() y pintar().
Si dos comparten esquina, se apilan en vez de taparse.
"""
from PySide6.QtCore import QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import estilo, sistema

MARGEN = 16
ALTO = 34
SEPARACION = 8  # entre dos pastillas apiladas en la misma esquina
POSICIONES = ["arriba-izquierda", "arriba-derecha", "abajo-izquierda", "abajo-derecha"]
NOMBRES_POSICIONES = ["Arriba izq.", "Arriba der.", "Abajo izq.", "Abajo der."]


class Pastilla(QWidget):
    _visibles = []  # pastillas en pantalla, en el orden en que aparecieron

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.posicion = "arriba-izquierda"
        self._opacidad = QVariantAnimation(self, duration=220, easingCurve=estilo.resorte(0))
        self._opacidad.valueChanged.connect(self.setWindowOpacity)
        self._opacidad.finished.connect(lambda: self.windowOpacity() < 0.01 and self._ocultar())
        # Algunos juegos se ponen encima al cambiar de ventana: la volvemos a subir de vez en cuando
        self._encima = QTimer(self, interval=2000)
        self._encima.timeout.connect(lambda: sistema.siempre_encima(int(self.winId())))

    def aparecer(self):
        if self not in Pastilla._visibles:
            Pastilla._visibles.append(self)
        if not self.isVisible():
            self.setWindowOpacity(0.0)
        self.colocar()
        self.show()
        sistema.siempre_encima(int(self.winId()))
        self._encima.start()
        self._ir_a(1.0)

    def desaparecer(self):
        self._encima.stop()
        self._ir_a(0.0)

    def _ocultar(self):
        self.hide()
        if self in Pastilla._visibles:
            Pastilla._visibles.remove(self)
        for otra in Pastilla._visibles:
            otra.colocar()

    def _ir_a(self, valor):
        self._opacidad.stop()
        if estilo.BAJO_CONSUMO:
            self.setWindowOpacity(valor)
            if valor <= 0:
                self._ocultar()
            return
        self._opacidad.setStartValue(self.windowOpacity())
        self._opacidad.setEndValue(valor)
        self._opacidad.start()

    def refrescar(self):
        """Vuelve a medir y dibujar (el contenido cambió)."""
        self.colocar()
        self.update()

    def colocar(self):
        ancho = int(self.ancho_contenido())
        self.resize(ancho, ALTO + 8)
        pantalla = QGuiApplication.primaryScreen()
        zona = pantalla.geometry()
        antes = [p for p in Pastilla._visibles[:Pastilla._visibles.index(self)] if p.posicion == self.posicion] \
            if self in Pastilla._visibles else []
        hueco = len(antes) * (ALTO + SEPARACION)
        x = zona.left() + MARGEN if "izquierda" in self.posicion else zona.right() - ancho - MARGEN
        y = zona.top() + MARGEN + hueco if "arriba" in self.posicion else \
            pantalla.availableGeometry().bottom() - ALTO - 8 - MARGEN - hueco
        self.move(x, y)

    # --- lo que cambia en cada pastilla
    def ancho_contenido(self):
        return 80

    def pintar(self, p, caja):
        """Dibuja el contenido dentro de caja (la cápsula, en coordenadas de la ventana)."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        caja = QRectF(1, 1, self.width() - 2, ALTO)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRoundedRect(caja.translated(0, 2), ALTO / 2, ALTO / 2)
        p.setPen(QPen(QColor(255, 255, 255, 32), 1))
        p.setBrush(QColor(22, 22, 24, 205))
        p.drawRoundedRect(caja, ALTO / 2, ALTO / 2)
        self.pintar(p, caja)
