"""La rueda que aparece al arrastrar un archivo y pulsar la tecla."""
import ctypes
import logging
import math
import os
from ctypes import wintypes

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from ... import estilo, sistema
from ...sistema import HOOKPROC, KBDLLHOOKSTRUCT, WH_KEYBOARD_LL, WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP
from ...sistema import kernel32, user32
from . import acciones


class GanchoTeclado(QObject):
    """Escucha una tecla en todo Windows y se la 'come' solo cuando toca abrir la rueda."""
    tecla = Signal()

    def __init__(self, vk, interceptar):
        super().__init__()
        self.vk = vk
        self._interceptar = interceptar
        self._comiendo = False
        self._proc = HOOKPROC(self._callback)  # guardar la referencia o Python la libera
        self._gancho = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not self._gancho:
            raise ctypes.WinError(ctypes.get_last_error())

    def _callback(self, codigo, wparam, lparam):
        try:
            tecla = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if codigo == 0 and tecla.vkCode == self.vk:
                if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if self._comiendo:  # tecla mantenida (autorrepetición)
                        return 1
                    if self._interceptar():
                        self._comiendo = True
                        QTimer.singleShot(0, self.tecla.emit)  # fuera del gancho, que debe responder rápido
                        return 1
                elif wparam in (WM_KEYUP, WM_SYSKEYUP) and self._comiendo:
                    self._comiendo = False
                    return 1
        except Exception:
            logging.exception("Error en el gancho de teclado")
        return user32.CallNextHookEx(self._gancho, codigo, wparam, lparam)

    def quitar(self):
        user32.UnhookWindowsHookEx(self._gancho)


class Rueda(QWidget):
    accion_elegida = Signal(object, list)

    TAM, R_INT, R_EXT = 380, 62, 158

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setFixedSize(self.TAM, self.TAM)
        self.rutas, self.acciones, self.encima, self.progreso = [], [], -1, 0.0
        self.recibio_arrastre = False
        self.fondo = None  # captura desenfocada de lo que hay detrás (el "vidrio")
        self.paleta = estilo.paleta()

        self.apertura = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=320,
                                          easingCurve=estilo.resorte(1.2))
        self.apertura.valueChanged.connect(self._animar)
        # El resaltado se desvanece suavemente al pasar de una opción a otra
        self.resaltado, self.resaltado_previo, self.brillo = -1, -1, 1.0
        self.transicion = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=140)
        self.transicion.valueChanged.connect(self._brillo)
        self.vigilante = QTimer(self, interval=60)
        self.vigilante.timeout.connect(self._vigilar_boton)
        self._ticks_sin_boton = 0

    # --- mostrar / ocultar
    def mostrar(self, pos):
        self.rutas, self.acciones, self.encima, self.recibio_arrastre = [], [], -1, False
        self.resaltado = self.resaltado_previo = -1
        self.paleta = estilo.paleta()
        self._ticks_sin_boton = 0
        x, y = pos.x() - self.TAM // 2, pos.y() - self.TAM // 2
        try:
            self.fondo = estilo.capturar_fondo(x, y, self.TAM, self.TAM)
        except Exception:
            logging.exception("No se pudo capturar el fondo")
            self.fondo = None
        self.move(x, y)
        self.show()
        self.raise_()
        self.apertura.start()
        self.vigilante.start()
        # El arrastre de Windows solo "ve" la ventana nueva cuando el ratón se mueve: lo empujamos 1 px
        QTimer.singleShot(60, lambda: self._empujar_cursor(1))
        QTimer.singleShot(110, lambda: self._empujar_cursor(-1))

    def ocultar(self):
        self.vigilante.stop()
        self.apertura.stop()
        self.hide()

    def _empujar_cursor(self, dx):
        punto = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(punto))
        user32.SetCursorPos(punto.x + dx, punto.y)

    def _animar(self, valor):
        self.progreso = valor
        self.update()

    def _brillo(self, valor):
        self.brillo = valor
        self.update()

    def _vigilar_boton(self):
        # Si sueltas fuera de la rueda o cancelas con Esc, se cierra sola
        self._ticks_sin_boton = 0 if sistema.boton_izquierdo_presionado() else self._ticks_sin_boton + 1
        if self._ticks_sin_boton >= 4:
            self.ocultar()

    # --- arrastrar y soltar
    def _indice_en(self, pos):
        dx, dy = pos.x() - self.TAM / 2, pos.y() - self.TAM / 2
        distancia = math.hypot(dx, dy)
        if not self.acciones or distancia < self.R_INT or distancia > self.R_EXT + 20:
            return -1
        angulo = math.degrees(math.atan2(dx, -dy)) % 360  # 0° arriba, sentido horario
        tramo = 360 / len(self.acciones)
        return int(((angulo + tramo / 2) % 360) // tramo)

    def _resaltar(self, indice):
        if indice != self.resaltado:
            self.resaltado_previo, self.resaltado = self.resaltado, indice
            self.transicion.start()

    def dragEnterEvent(self, evento):
        if not self.recibio_arrastre:
            self.recibio_arrastre = True
            rutas = [os.path.normpath(u.toLocalFile()) for u in evento.mimeData().urls() if u.isLocalFile()]
            self.rutas = [r for r in rutas if os.path.exists(r)]
            self.acciones = acciones.acciones_para(self.rutas) if self.rutas else []
            logging.info("Arrastre: %s -> %s", self.rutas, [a.nombre for a in self.acciones])
        evento.setDropAction(Qt.CopyAction)
        evento.accept()
        self.update()

    def dragMoveEvent(self, evento):
        indice = self._indice_en(evento.position())
        if indice != self.encima:
            self.encima = indice
            self._resaltar(indice)
        if indice >= 0:
            evento.setDropAction(Qt.CopyAction)  # copiar: el Explorador nunca borra el original
            evento.accept()
        else:
            evento.ignore()

    def dragLeaveEvent(self, evento):
        self.encima = -1
        self._resaltar(-1)

    def dropEvent(self, evento):
        indice = self._indice_en(evento.position())
        if indice >= 0:
            evento.setDropAction(Qt.CopyAction)
            evento.accept()
            self.accion_elegida.emit(self.acciones[indice], list(self.rutas))
        self.ocultar()

    # --- dibujo
    def _punto(self, angulo, radio):
        a = math.radians(angulo)
        return QPointF(self.TAM / 2 + radio * math.sin(a), self.TAM / 2 - radio * math.cos(a))

    def _sector(self, inicio, fin, r_int, r_ext):
        pasos = max(8, int(abs(fin - inicio) / 3))
        exterior = [self._punto(inicio + (fin - inicio) * i / pasos, r_ext) for i in range(pasos + 1)]
        interior = [self._punto(fin - (fin - inicio) * i / pasos, r_int) for i in range(pasos + 1)]
        return QPolygonF(exterior + interior)

    def _circulo(self, radio):
        camino = QPainterPath()
        camino.addEllipse(QPointF(self.TAM / 2, self.TAM / 2), radio, radio)
        return camino

    def _pintar_resaltado(self, p, indice, intensidad, r_int, r_ext, tramo):
        if not 0 <= indice < len(self.acciones) or intensidad <= 0:
            return
        color = QColor(self.acciones[indice].color)
        color.setAlphaF(0.92 * intensidad)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        a = indice * tramo
        hueco = 1.2 if len(self.acciones) > 1 else 0
        p.drawPolygon(self._sector(a - tramo / 2 + hueco, a + tramo / 2 - hueco, r_int + 4, r_ext - 4))

    def paintEvent(self, _):
        pal = self.paleta
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        centro = QPointF(self.TAM / 2, self.TAM / 2)

        # Disco casi invisible: Windows ignora los píxeles 100% transparentes al arrastrar
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 2))
        p.drawEllipse(centro, self.R_EXT + 22, self.R_EXT + 22)

        t = self.progreso
        p.setOpacity(max(0.0, min(1.0, t * 1.6)))
        escala = 0.86 + 0.14 * t
        r_ext, r_int = self.R_EXT * escala, self.R_INT * escala
        disco = self._circulo(r_ext)

        sombra = QRadialGradient(centro, r_ext + 20)
        sombra.setColorAt(r_ext / (r_ext + 20) - 0.03, QColor(0, 0, 0, 70 if pal.oscuro else 45))
        sombra.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(sombra)
        p.drawEllipse(centro, r_ext + 20, r_ext + 20)

        # Vidrio: fondo desenfocado + tinte del tema + brillo arriba
        p.save()
        p.setClipPath(disco)
        if self.fondo is not None:
            p.drawPixmap(0, 0, self.fondo)
        p.fillPath(disco, QColor(*pal.vidrio))
        brillo = QLinearGradient(0, centro.y() - r_ext, 0, centro.y() + r_ext)
        brillo.setColorAt(0.0, QColor(255, 255, 255, 50 if pal.oscuro else 90))
        brillo.setColorAt(0.55, QColor(255, 255, 255, 0))
        p.fillPath(disco, brillo)

        n = len(self.acciones)
        tramo = 360 / max(n, 1)
        self._pintar_resaltado(p, self.resaltado_previo, 1 - self.brillo, r_int, r_ext, tramo)
        self._pintar_resaltado(p, self.resaltado, self.brillo, r_int, r_ext, tramo)
        p.restore()

        # Líneas finas entre opciones
        linea = QColor(pal.texto)
        linea.setAlpha(28)
        if n > 1:
            p.setPen(QPen(linea, 1))
            for i in range(n):
                a = i * tramo + tramo / 2
                p.drawLine(self._punto(a, r_int + 10), self._punto(a, r_ext - 10))

        # Borde de cristal
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 60 if pal.oscuro else 200), 1))
        p.drawEllipse(centro, r_ext - 1, r_ext - 1)
        p.setPen(QPen(QColor(0, 0, 0, 70 if pal.oscuro else 30), 1))
        p.drawEllipse(centro, r_ext, r_ext)

        # Textos
        for i, accion in enumerate(self.acciones):
            activa = i == self.resaltado
            punto = self._punto(i * tramo, (r_int + r_ext) / 2)
            f = estilo.fuente(11, QFont.DemiBold if activa else QFont.Medium)
            p.setFont(f)
            color = estilo.mezclar(pal.texto, "#FFFFFF", self.brillo if activa else 0)
            if i == self.resaltado_previo:
                color = estilo.mezclar("#FFFFFF", pal.texto, self.brillo)
            p.setPen(color)
            p.drawText(QRectF(punto.x() - 45, punto.y() - 12, 90, 24), Qt.AlignCenter, accion.nombre)

        # Centro
        r_centro = r_int - 8 * escala
        fondo_centro = QColor(pal.superficie)
        fondo_centro.setAlpha(150 if pal.oscuro else 190)
        p.setPen(QPen(linea, 1))
        p.setBrush(fondo_centro)
        p.drawEllipse(centro, r_centro, r_centro)
        if 0 <= self.encima < n:
            mensaje = self.acciones[self.encima].descripcion
        elif not self.recibio_arrastre:
            mensaje = "Mueve el ratón"
        elif not self.rutas:
            mensaje = "Nada que hacer con esto"
        else:
            cantidad = len(self.rutas)
            mensaje = f"{cantidad} elemento{'s' if cantidad > 1 else ''}"
        p.setPen(QColor(pal.texto2))
        p.setFont(estilo.fuente(8.5, QFont.Medium))
        caja = QRectF(centro.x() - r_centro + 7, centro.y() - r_centro + 7, 2 * r_centro - 14, 2 * r_centro - 14)
        p.drawText(caja, Qt.AlignCenter | Qt.TextWordWrap, mensaje)
