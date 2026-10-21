"""La pastilla del Pomodoro: fase, tiempo restante y los enfoques hechos del ciclo."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF

from ... import estilo
from ...pastilla import ALTO, Pastilla
from .temporizador import CICLO, ENFOQUE, LARGO, NOMBRES

COLORES = {ENFOQUE: "#FF453A", "corto": "#30D158", LARGO: "#0A84FF"}


class PastillaPomodoro(Pastilla):
    def __init__(self, temporizador):
        super().__init__()
        self.temporizador = temporizador
        self.posicion = "abajo-derecha"
        self.fuente_reloj = estilo.fuente(13, QFont.DemiBold, titulo=True)
        self.fuente_etiqueta = estilo.fuente(7.5, QFont.DemiBold)

    def _medidas(self):
        t = self.temporizador
        etiqueta = NOMBRES[t.fase].upper()
        m_reloj, m_eti = QFontMetricsF(self.fuente_reloj), QFontMetricsF(self.fuente_etiqueta)
        return etiqueta, m_eti.horizontalAdvance(etiqueta), max(m_reloj.horizontalAdvance("00:00"),
                                                              m_reloj.horizontalAdvance(t.reloj()))

    def ancho_contenido(self):
        _, ancho_eti, ancho_reloj = self._medidas()
        return 15 + 9 + 8 + ancho_eti + 8 + ancho_reloj + 12 + CICLO * 7 + 12

    def pintar(self, p, caja):
        t = self.temporizador
        etiqueta, ancho_eti, ancho_reloj = self._medidas()
        medio = caja.center().y()
        x = 15.0
        color = QColor(COLORES[t.fase])
        if t.corriendo:  # punto del color de la fase
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(x + 4.5, medio), 4.5, 4.5)
        else:  # en pausa: dos barras
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 170))
            p.drawRoundedRect(QRectF(x + 1, medio - 5, 2.6, 10), 1.2, 1.2)
            p.drawRoundedRect(QRectF(x + 5.6, medio - 5, 2.6, 10), 1.2, 1.2)
        x += 9 + 8
        p.setFont(self.fuente_etiqueta)
        p.setPen(QColor(255, 255, 255, 140))
        p.drawText(QRectF(x, caja.top() + 1, ancho_eti + 2, ALTO), Qt.AlignVCenter | Qt.AlignLeft, etiqueta)
        x += ancho_eti + 8
        p.setFont(self.fuente_reloj)
        p.setPen(QColor(255, 255, 255, 255 if t.corriendo else 150))
        p.drawText(QRectF(x, caja.top(), ancho_reloj, ALTO), Qt.AlignVCenter | Qt.AlignLeft, t.reloj())
        x += ancho_reloj + 12
        hechos = t.en_ciclo()
        for i in range(CICLO):
            p.setBrush(QColor(COLORES[ENFOQUE]) if i < hechos else QColor(255, 255, 255, 45))
            p.drawEllipse(QPointF(x + 2.5 + i * 7, medio), 2.5, 2.5)
