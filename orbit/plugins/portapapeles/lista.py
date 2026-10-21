"""La lista del historial: un panel de vidrio junto al cursor, con buscador y navegación con el teclado."""
import time

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from ... import estilo

SOMBRA, RADIO = 14, 14
ANCHO = 380
ALTO_FILA = 48
FILAS_VISIBLES = 7
MINIATURA = (52, 34)  # puntos


def hace(hora):
    segundos = time.time() - hora
    if segundos < 60:
        return "Ahora"
    if segundos < 3600:
        return f"Hace {int(segundos // 60)} min"
    if segundos < 86400:
        return f"Hace {int(segundos // 3600)} h"
    dias = int(segundos // 86400)
    return "Ayer" if dias == 1 else f"Hace {dias} días"


def una_linea(texto):
    return " ".join(texto.split())


class Buscador(QLineEdit):
    """Campo de búsqueda: las flechas, Enter, Esc y los atajos de la lista no se escriben, van a la lista."""

    def __init__(self, lista):
        super().__init__()
        self.lista = lista
        self.setPlaceholderText("Buscar en el historial")

    def keyPressEvent(self, evento):
        if not self.lista.tecla(evento):
            super().keyPressEvent(evento)


class Filas(QWidget):
    """Los elementos, dibujados a mano (como el resto de Orbit)."""

    def __init__(self, lista):
        super().__init__()
        self.lista = lista
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def _indice(self, pos):
        i = int(pos.y() // ALTO_FILA)
        return i if 0 <= i < len(self.lista.visibles) else -1

    def _en_chincheta(self, pos):
        return pos.x() >= self.width() - 40

    def mouseMoveEvent(self, evento):
        i = self._indice(evento.position())
        if i >= 0 and i != self.lista.indice:
            self.lista.seleccionar(i, desplazar=False)

    def mouseReleaseEvent(self, evento):
        i = self._indice(evento.position())
        if evento.button() != Qt.LeftButton or i < 0:
            return
        if self._en_chincheta(evento.position()):
            self.lista.alternar_fijado(i)
        else:
            self.lista.elegir(i)

    def paintEvent(self, _):
        self.lista.pintar_filas(QPainter(self), self.width())


class Lista(QWidget):
    elegido = Signal(dict)
    fijado = Signal(str, bool)
    quitado = Signal(str)

    def __init__(self, historial):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.historial = historial
        self.visibles, self.indice = [], 0
        self.miniaturas = {}  # clave -> QPixmap
        self.paleta = estilo.paleta()
        self.fondo = None
        self.anterior = 0  # la ventana que tenía el foco antes de abrir la lista
        self.setFixedWidth(ANCHO + 2 * SOMBRA)
        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(SOMBRA + 10, SOMBRA + 10, SOMBRA + 10, SOMBRA + 8)
        diseno.setSpacing(8)
        self.buscador = Buscador(self)
        self.buscador.textChanged.connect(self._filtrar)
        diseno.addWidget(self.buscador)
        self.filas = Filas(self)
        self.desplazable = QScrollArea()
        self.desplazable.setWidgetResizable(True)
        self.desplazable.setFrameShape(QScrollArea.NoFrame)
        self.desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.desplazable.setWidget(self.filas)
        diseno.addWidget(self.desplazable)
        pie = QLabel("↑↓ elegir  ·  Enter pegar  ·  Ctrl+P fijar  ·  Supr quitar  ·  Esc cerrar")
        pie.setObjectName("secundario")
        pie.setFont(estilo.fuente(8))
        pie.setAlignment(Qt.AlignCenter)
        diseno.addWidget(pie)
        self._estilo()

    def _estilo(self):
        p = self.paleta
        campo = "rgba(255,255,255,0.08)" if p.oscuro else "rgba(255,255,255,0.7)"
        self.setStyleSheet(estilo.hoja_de_estilo(p) + f"""
            QLineEdit {{ background: {campo}; border: 1px solid {p.separador}; border-radius: 8px;
                         padding: 6px 10px; font-size: 10.5pt; selection-background-color: {p.acento}; }}""")

    # --- abrir y cerrar
    def abrir(self, pos, anterior):
        self.anterior = anterior
        paleta = estilo.paleta()
        if paleta != self.paleta:
            self.paleta = paleta
            self._estilo()
        self.buscador.blockSignals(True)
        self.buscador.clear()
        self.buscador.blockSignals(False)
        self._filtrar("")
        # El alto se fija al abrir: al buscar, la lista no da saltos
        self.desplazable.setFixedHeight(max(1, min(len(self.visibles), FILAS_VISIBLES)) * ALTO_FILA)
        self.adjustSize()
        pantalla = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        zona = pantalla.availableGeometry()
        x = min(max(zona.left() - SOMBRA, pos.x() - SOMBRA - 24), zona.right() - self.width() + SOMBRA)
        y = pos.y() + 14 - SOMBRA
        if y + self.height() - SOMBRA > zona.bottom():  # no cabe debajo del cursor: va encima
            y = pos.y() - 14 - self.height() + SOMBRA
        y = max(zona.top() - SOMBRA, y)
        self.fondo = None
        if not estilo.BAJO_CONSUMO:
            try:
                self.fondo = estilo.capturar_fondo(x, y, self.width(), self.height())
            except Exception:
                pass
        self.move(x, y)
        estilo.animar_aparicion(self, desplazamiento=8)
        self.activateWindow()
        self.buscador.setFocus()

    def refrescar(self):
        """Tras fijar o quitar: misma búsqueda y, si sigue, el mismo elemento elegido."""
        clave = self.visibles[self.indice]["clave"] if self.visibles else None
        self._filtrar(self.buscador.text())
        claves = [e["clave"] for e in self.visibles]
        if clave in claves:
            self.seleccionar(claves.index(clave))
        vivas = {e["clave"] for e in self.historial.elementos}
        self.miniaturas = {c: m for c, m in self.miniaturas.items() if c in vivas}

    def _filtrar(self, texto):
        self.visibles = self.historial.ordenados(texto)
        self.indice = 0
        self.filas.setFixedHeight(max(1, len(self.visibles)) * ALTO_FILA)
        self.desplazable.verticalScrollBar().setValue(0)
        self.filas.update()

    # --- teclado y ratón
    def tecla(self, evento):
        k, control = evento.key(), bool(evento.modifiers() & Qt.ControlModifier)
        if k == Qt.Key_Escape:
            self.hide()
        elif k in (Qt.Key_Down, Qt.Key_Up):
            self.seleccionar(self.indice + (1 if k == Qt.Key_Down else -1))
        elif k in (Qt.Key_PageDown, Qt.Key_PageUp):
            self.seleccionar(self.indice + (FILAS_VISIBLES if k == Qt.Key_PageDown else -FILAS_VISIBLES))
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.elegir(self.indice)
        elif k == Qt.Key_P and control:
            self.alternar_fijado(self.indice)
        elif k == Qt.Key_Delete and self.buscador.cursorPosition() == len(self.buscador.text()):
            if self.visibles:
                self.quitado.emit(self.visibles[self.indice]["clave"])
        else:
            return False
        return True

    def seleccionar(self, indice, desplazar=True):
        if not self.visibles:
            return
        self.indice = max(0, min(len(self.visibles) - 1, indice))
        if desplazar:
            self.desplazable.ensureVisible(0, int((self.indice + 0.5) * ALTO_FILA), 0, ALTO_FILA // 2)
        self.filas.update()

    def elegir(self, indice):
        if 0 <= indice < len(self.visibles):
            elemento = self.visibles[indice]
            self.hide()
            self.elegido.emit(elemento)

    def alternar_fijado(self, indice):
        if 0 <= indice < len(self.visibles):
            elemento = self.visibles[indice]
            self.fijado.emit(elemento["clave"], not elemento["fijado"])

    # --- dibujo
    def paintEvent(self, _):
        estilo.pintar_vidrio(QPainter(self), self.rect(), SOMBRA, RADIO, self.fondo, self.paleta)

    def _miniatura(self, elemento):
        clave = elemento["clave"]
        if clave not in self.miniaturas:
            escala = self.devicePixelRatioF()
            imagen = QImage.fromData(elemento.get("mini") or elemento["png"])
            imagen = imagen.scaled(int(MINIATURA[0] * escala), int(MINIATURA[1] * escala), Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
            miniatura = QPixmap.fromImage(imagen)
            miniatura.setDevicePixelRatio(escala)
            self.miniaturas[clave] = miniatura
        return self.miniaturas[clave]

    def pintar_filas(self, p, ancho):
        pal = self.paleta
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self.visibles:
            p.setPen(QColor(pal.texto2))
            p.setFont(estilo.fuente(9.5))
            mensaje = "Nada coincide con la búsqueda" if self.buscador.text() else "Copia algo y aparecerá aquí"
            p.drawText(QRectF(0, 0, ancho, ALTO_FILA), Qt.AlignCenter, mensaje)
            return
        fuente_titulo, fuente_detalle = estilo.fuente(10), estilo.fuente(8.5)
        medida = QFontMetrics(fuente_titulo)
        for i, e in enumerate(self.visibles):
            caja = QRectF(0, i * ALTO_FILA, ancho, ALTO_FILA)
            elegida = i == self.indice
            if elegida:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(pal.acento))
                p.drawRoundedRect(caja.adjusted(0, 1, 0, -1), 9, 9)
            color = QColor("#FFFFFF") if elegida else QColor(pal.texto)
            color2 = QColor(255, 255, 255, 200) if elegida else QColor(pal.texto2)
            x = 12.0
            if e["tipo"] == "imagen":
                miniatura = self._miniatura(e)
                tam = miniatura.deviceIndependentSize()
                destino = QRectF(x + (MINIATURA[0] - tam.width()) / 2, caja.top() + (ALTO_FILA - tam.height()) / 2,
                                 tam.width(), tam.height())
                p.drawPixmap(destino, miniatura, QRectF(miniatura.rect()))
                x += MINIATURA[0] + 10
                titulo, detalle = "Imagen", f"{e['ancho']} × {e['alto']}  ·  {hace(e['hora'])}"
            else:
                titulo = una_linea(e["texto"])
                largo = len(e["texto"])
                detalle = hace(e["hora"]) + (f"  ·  {largo} caracteres" if largo > 60 else "")
            ancho_texto = ancho - x - 40
            p.setFont(fuente_titulo)
            p.setPen(color)
            p.drawText(QRectF(x, caja.top() + 6, ancho_texto, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       medida.elidedText(titulo, Qt.ElideRight, int(ancho_texto)))
            p.setFont(fuente_detalle)
            p.setPen(color2)
            p.drawText(QRectF(x, caja.top() + 25, ancho_texto, 16), Qt.AlignLeft | Qt.AlignVCenter, detalle)
            if e["fijado"] or elegida:  # en la elegida se ve tenue, como pista de que se puede fijar
                tono = QColor(color) if e["fijado"] else QColor(255, 255, 255, 110)
                if not elegida:
                    tono = QColor(pal.acento)
                estilo.dibujar_chincheta(p, QRectF(ancho - 32, caja.top() + 12, 22, 22), tono)
