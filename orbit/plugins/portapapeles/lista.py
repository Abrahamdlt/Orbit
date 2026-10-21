"""La lista del historial: un panel de vidrio junto al cursor, con buscador y navegación con el teclado.
Cada elemento se pega con Enter o un clic, o se arrastra a otra ventana o a una carpeta."""
import os
import tempfile
import time

from PySide6.QtCore import QFileInfo, QMimeData, QPoint, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileIconProvider, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from ... import estilo

SOMBRA, RADIO = 14, 14
ANCHO = 380
ALTO_FILA = 48
FILAS_VISIBLES = 7
MINIATURA = (52, 34)  # puntos
# Al arrastrar una imagen hace falta un archivo (las carpetas y muchos chats solo aceptan archivos)
CARPETA_TEMPORAL = os.path.join(tempfile.gettempdir(), "Orbit", "portapapeles")


def existentes(elemento):
    return [r for r in elemento["rutas"] if os.path.exists(r)]


def mime_de(elemento, arrastre=False):
    """Lo que se pone en el portapapeles o se arrastra. None si eran archivos y ya no existe ninguno."""
    mime = QMimeData()
    if elemento["tipo"] == "texto":
        mime.setText(elemento["texto"])
    elif elemento["tipo"] == "archivos":
        rutas = existentes(elemento)
        if not rutas:
            return None
        mime.setUrls([QUrl.fromLocalFile(r) for r in rutas])
    else:
        mime.setImageData(QImage.fromData(elemento["png"]))
        if arrastre:
            os.makedirs(CARPETA_TEMPORAL, exist_ok=True)
            ruta = os.path.join(CARPETA_TEMPORAL, f"Imagen {elemento['clave'][1:9]}.png")
            if not os.path.exists(ruta):
                with open(ruta, "wb") as f:
                    f.write(elemento["png"])
            mime.setUrls([QUrl.fromLocalFile(ruta)])
    return mime


def nombre(ruta):
    """Nombre del archivo o carpeta. Una unidad (C:\\) no tiene nombre: se muestra entera."""
    return os.path.basename(ruta.rstrip("\\/")) or ruta


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
        self.pulsado = None  # (posición, índice) al apretar el botón: si se mueve lejos, se arrastra
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def _indice(self, pos):
        i = int(pos.y() // ALTO_FILA)
        return i if 0 <= i < len(self.lista.visibles) else -1

    def _en_chincheta(self, pos):
        return pos.x() >= self.width() - 40

    def mousePressEvent(self, evento):
        i = self._indice(evento.position())
        if evento.button() == Qt.LeftButton and i >= 0:
            self.pulsado = (evento.position().toPoint(), i)

    def mouseMoveEvent(self, evento):
        if self.pulsado and evento.buttons() & Qt.LeftButton:
            inicio, i = self.pulsado
            if (evento.position().toPoint() - inicio).manhattanLength() >= QApplication.startDragDistance():
                self.pulsado = None
                self.lista.arrastrar(i)
            return
        i = self._indice(evento.position())
        if i >= 0 and i != self.lista.indice:
            self.lista.seleccionar(i, desplazar=False)

    def mouseReleaseEvent(self, evento):
        pulsado, self.pulsado = self.pulsado, None
        i = self._indice(evento.position())
        if evento.button() != Qt.LeftButton or i < 0 or pulsado is None:  # sin pulsado: fue un arrastre
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
    no_existe = Signal()  # se quiso arrastrar un archivo que ya no está

    def __init__(self, historial):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.historial = historial
        self.visibles, self.indice = [], 0
        self.miniaturas = {}  # clave -> QPixmap (miniatura de imagen o icono de archivo)
        self.existen = {}     # clave -> True si sus archivos siguen ahí (se mira al abrir y al buscar)
        self.iconos = QFileIconProvider()
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
        self.existen = {e["clave"]: bool(existentes(e)) for e in self.visibles if e["tipo"] == "archivos"}
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

    def arrastrar(self, indice):
        """Arrastra el elemento fuera de la lista: archivos a una carpeta, texto o imagen a otra ventana."""
        elemento = self.visibles[indice]
        mime = mime_de(elemento, arrastre=True)
        if mime is None:
            self.no_existe.emit()
            return
        arrastre = QDrag(self.filas)
        arrastre.setMimeData(mime)
        arrastre.setPixmap(self._imagen_arrastre(elemento))
        arrastre.setHotSpot(QPoint(-12, -12))
        if arrastre.exec(Qt.CopyAction) != Qt.IgnoreAction:  # lo soltó en algún sitio: la lista ya no hace falta
            self.hide()

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
            if elemento["tipo"] == "archivos":  # el icono de Windows del primero (carpeta, PDF, Word...)
                miniatura = self.iconos.icon(QFileInfo(elemento["rutas"][0])).pixmap(32, 32)
            else:
                imagen = QImage.fromData(elemento.get("mini") or elemento["png"])
                imagen = imagen.scaled(int(MINIATURA[0] * escala), int(MINIATURA[1] * escala), Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
                miniatura = QPixmap.fromImage(imagen)
                miniatura.setDevicePixelRatio(escala)
            self.miniaturas[clave] = miniatura
        return self.miniaturas[clave]

    def _imagen_arrastre(self, elemento):
        """Lo que se ve junto al cursor mientras se arrastra."""
        if elemento["tipo"] != "texto":
            return self._miniatura(elemento)
        texto = QFontMetrics(estilo.fuente(9.5)).elidedText(una_linea(elemento["texto"]), Qt.ElideRight, 220)
        escala = self.devicePixelRatioF()
        imagen = QPixmap(int(240 * escala), int(30 * escala))
        imagen.setDevicePixelRatio(escala)
        imagen.fill(Qt.transparent)
        p = QPainter(imagen)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.paleta.acento))
        p.drawRoundedRect(QRectF(0, 0, 240, 30), 9, 9)
        p.setPen(Qt.white)
        p.setFont(estilo.fuente(9.5))
        p.drawText(QRectF(10, 0, 222, 30), Qt.AlignVCenter | Qt.AlignLeft, texto)
        p.end()
        return imagen

    def _pintar_miniatura(self, p, elemento, caja, x):
        miniatura = self._miniatura(elemento)
        tam = miniatura.deviceIndependentSize()
        destino = QRectF(x + (MINIATURA[0] - tam.width()) / 2, caja.top() + (ALTO_FILA - tam.height()) / 2,
                         tam.width(), tam.height())
        p.drawPixmap(destino, miniatura, QRectF(miniatura.rect()))
        n = len(elemento.get("rutas", ()))
        if n > 1:  # varios archivos: el número en una burbuja sobre el icono
            burbuja = QRectF(destino.right() - 9, destino.bottom() - 13, 18, 16)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.paleta.rojo))
            p.drawRoundedRect(burbuja, 8, 8)
            p.setPen(Qt.white)
            p.setFont(estilo.fuente(7.5, QFont.DemiBold))
            p.drawText(burbuja, Qt.AlignCenter, str(n) if n < 100 else "99+")

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
                self._pintar_miniatura(p, e, caja, x)
                x += MINIATURA[0] + 10
                titulo, detalle = "Imagen", f"{e['ancho']} × {e['alto']}  ·  {hace(e['hora'])}"
            elif e["tipo"] == "archivos":
                self._pintar_miniatura(p, e, caja, x)
                x += MINIATURA[0] + 10
                rutas = e["rutas"]
                titulo = nombre(rutas[0]) + (f" y {len(rutas) - 1} más" if len(rutas) > 1 else "")
                carpeta = nombre(os.path.dirname(rutas[0].rstrip("\\/")))
                detalle = carpeta if self.existen.get(e["clave"], True) else "Ya no existe"
                detalle += f"  ·  {hace(e['hora'])}"
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
