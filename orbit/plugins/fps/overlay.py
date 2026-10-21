"""El medidor flotante: una pastilla oscura y discreta encima de todas las ventanas."""
from PySide6.QtCore import QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ... import estilo, sistema

MARGEN = 16
ALTO = 34


class Medidor(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.lectura = {}
        self.metricas = {"fps": True, "cpu": True, "gpu": True, "ram": True}
        self.posicion = "arriba-izquierda"
        self.fuente_numero = estilo.fuente(13, QFont.DemiBold, titulo=True)
        self.fuente_valor = estilo.fuente(10, QFont.DemiBold)
        self.fuente_etiqueta = estilo.fuente(7.5, QFont.DemiBold)
        self._opacidad = QVariantAnimation(self, duration=220, easingCurve=estilo.resorte(0))
        self._opacidad.valueChanged.connect(self.setWindowOpacity)
        self._opacidad.finished.connect(lambda: self.windowOpacity() < 0.01 and self.hide())
        # Algunos juegos se ponen encima al cambiar de ventana: lo volvemos a subir de vez en cuando
        self._encima = QTimer(self, interval=2000)
        self._encima.timeout.connect(lambda: sistema.siempre_encima(int(self.winId())))

    def aparecer(self):
        self.setWindowOpacity(0.0)
        self._colocar()
        self.show()
        sistema.siempre_encima(int(self.winId()))
        self._encima.start()
        self._ir_a(1.0)

    def desaparecer(self):
        self._encima.stop()
        self._ir_a(0.0)

    def _ir_a(self, valor):
        self._opacidad.stop()
        self._opacidad.setStartValue(self.windowOpacity())
        self._opacidad.setEndValue(valor)
        self._opacidad.start()

    def actualizar(self, lectura):
        self.lectura = lectura
        self._colocar()
        self.update()

    # --- contenido: [(etiqueta, valor principal, valor secundario)]
    def _segmentos(self):
        l = self.lectura

        def pct(clave):
            return f"{l[clave]:.0f}%" if l.get(clave) is not None else "—"

        def grados(clave):
            return f"{l[clave]:.0f}°" if l.get(clave) is not None else ""

        segmentos = []
        if self.metricas.get("fps"):
            segmentos.append(("FPS", f"{l['fps']:.0f}" if l.get("fps") else "—", ""))
        if self.metricas.get("cpu"):
            segmentos.append(("CPU", pct("cpu_uso"), grados("cpu_temp")))
        if self.metricas.get("gpu"):
            segmentos.append(("GPU", pct("gpu_uso"), grados("gpu_temp")))
        if self.metricas.get("ram"):
            segmentos.append(("RAM", pct("ram_uso"), ""))
        return segmentos

    def _medidas(self):
        m_num, m_val, m_eti = (QFontMetricsF(f) for f in (self.fuente_numero, self.fuente_valor, self.fuente_etiqueta))
        anchos = []
        for i, (etiqueta, valor, extra) in enumerate(self._segmentos()):
            if etiqueta == "FPS":
                ancho = max(m_num.horizontalAdvance("000"), m_num.horizontalAdvance(valor)) + 5 \
                    + m_eti.horizontalAdvance("FPS")
            else:
                ancho = m_eti.horizontalAdvance(etiqueta) + 6 + max(m_val.horizontalAdvance("100%"),
                                                                    m_val.horizontalAdvance(valor))
                if extra:
                    ancho += 5 + max(m_val.horizontalAdvance("100°"), m_val.horizontalAdvance(extra))
            anchos.append(ancho)
        return anchos

    def _colocar(self):
        anchos = self._medidas()
        ancho = int(sum(anchos) + 26 * max(0, len(anchos) - 1) + 28) if anchos else 80
        self.resize(ancho, ALTO + 8)
        pantalla = QGuiApplication.primaryScreen()
        zona = pantalla.geometry()
        x = zona.left() + MARGEN if "izquierda" in self.posicion else zona.right() - ancho - MARGEN
        y = zona.top() + MARGEN if "arriba" in self.posicion else \
            pantalla.availableGeometry().bottom() - ALTO - 8 - MARGEN
        self.move(x, y)

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

        blanco, gris = QColor(255, 255, 255), QColor(255, 255, 255, 140)
        m_num, m_val, m_eti = (QFontMetricsF(f) for f in (self.fuente_numero, self.fuente_valor, self.fuente_etiqueta))
        x, medio = 15.0, caja.center().y()
        for i, ((etiqueta, valor, extra), ancho) in enumerate(zip(self._segmentos(), self._medidas())):
            if i:
                p.setPen(QPen(QColor(255, 255, 255, 30), 1))
                p.drawLine(x - 13, medio - 8, x - 13, medio + 8)
            if etiqueta == "FPS":
                p.setFont(self.fuente_numero)
                p.setPen(blanco)
                ancho_num = max(m_num.horizontalAdvance("000"), m_num.horizontalAdvance(valor))
                p.drawText(QRectF(x, caja.top(), ancho_num, ALTO), Qt.AlignVCenter | Qt.AlignRight, valor)
                p.setFont(self.fuente_etiqueta)
                p.setPen(gris)
                p.drawText(QRectF(x + ancho_num + 5, caja.top() + 1, 40, ALTO), Qt.AlignVCenter | Qt.AlignLeft, "FPS")
            else:
                p.setFont(self.fuente_etiqueta)
                p.setPen(gris)
                ancho_eti = m_eti.horizontalAdvance(etiqueta)
                p.drawText(QRectF(x, caja.top() + 1, ancho_eti, ALTO), Qt.AlignVCenter | Qt.AlignLeft, etiqueta)
                p.setFont(self.fuente_valor)
                p.setPen(blanco)
                x_val = x + ancho_eti + 6
                ancho_val = max(m_val.horizontalAdvance("100%"), m_val.horizontalAdvance(valor))
                p.drawText(QRectF(x_val, caja.top(), ancho_val, ALTO), Qt.AlignVCenter | Qt.AlignRight, valor)
                if extra:
                    p.setPen(QColor(255, 255, 255, 175))
                    p.drawText(QRectF(x_val + ancho_val + 5, caja.top(), 50, ALTO), Qt.AlignVCenter | Qt.AlignLeft,
                               extra)
            x += ancho + 26
