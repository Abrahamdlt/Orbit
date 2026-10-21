"""El medidor flotante: una pastilla con FPS, CPU, GPU y RAM encima de todas las ventanas."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPen

from ... import estilo
from ...pastilla import ALTO, Pastilla


class Medidor(Pastilla):
    def __init__(self):
        super().__init__()
        self.lectura = {}
        self.metricas = {"fps": True, "cpu": True, "gpu": True, "ram": True}
        self.fuente_numero = estilo.fuente(13, QFont.DemiBold, titulo=True)
        self.fuente_valor = estilo.fuente(10, QFont.DemiBold)
        self.fuente_etiqueta = estilo.fuente(7.5, QFont.DemiBold)

    def actualizar(self, lectura):
        self.lectura = lectura
        self.refrescar()

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

    def ancho_contenido(self):
        anchos = self._medidas()
        return sum(anchos) + 26 * max(0, len(anchos) - 1) + 28 if anchos else 80

    def pintar(self, p, caja):
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
