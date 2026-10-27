"""Video de demostración de Orbit: las piezas reales de la app (panel, rueda, medidor, avisos, ajustes...)
animadas cuadro a cuadro sobre un escritorio de Windows dibujado.

Uso:
    python demo/video_demo.py                 # renderiza demo/Orbit-demo.mp4
    python demo/video_demo.py --fotos 2 9 15  # guarda fotogramas sueltos (segundos) en demo/fotos para revisar
Necesita: pip install imageio-ffmpeg (trae FFmpeg)
"""
import copy
import math
import os
import random
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient, QRegion)
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)

from orbit import estilo, sistema

sistema.tema_oscuro = lambda: True  # el video va en modo oscuro
estilo.BAJO_CONSUMO = False
app.setFont(estilo.fuente(10))

from orbit import config as modulo_config
from orbit.ajustes import VentanaAjustes
from orbit.config import Config
from orbit.panel import SOMBRA as SOMBRA_PANEL
from orbit.panel import Panel
from orbit.pantalla import SelectorPantalla, _Lienzo
from orbit.plugins import CLASES
from orbit.plugins.fps.overlay import Medidor
from orbit.plugins.pomodoro.temporizador import Temporizador
from orbit.plugins.pomodoro.vista import PastillaPomodoro
from orbit.plugins.portapapeles.historial import Historial
from orbit.plugins.portapapeles.lista import SOMBRA as SOMBRA_LISTA
from orbit.plugins.portapapeles.lista import Lista
from orbit.plugins.radial import acciones
from orbit.plugins.radial.rueda import Rueda

W, H = 1280, 720          # escritorio "lógico"
ESCALA = 1.5               # se renderiza a 1920 × 1080, como una pantalla al 150 %
FPS = 30
BARRA = 48                 # alto de la barra de tareas
FUNDIDO = 0.4              # segundos de transición entre escenas
BANDEJA = QPointF(1131, H - BARRA / 2)  # icono de Orbit junto al reloj
SALIDA = os.path.join(RAIZ, "demo")


# ---------------------------------------------------------------- utilidades de animación

def tramo(t, a, b):
    return 0.0 if t <= a else 1.0 if t >= b else (t - a) / (b - a)


def suave(x):
    return x * x * (3 - 2 * x)


def salida(x):
    return 1 - (1 - x) ** 3


_curvas = {}


def rebote(x, cantidad=1.2):
    if cantidad not in _curvas:
        _curvas[cantidad] = estilo.resorte(cantidad)
    return _curvas[cantidad].valueForProgress(max(0.0, min(1.0, x)))


def mezcla(a, b, k):
    return a + (b - a) * k


def camino(t, puntos):
    """Posición en un recorrido [(tiempo, x, y), ...] con movimientos suaves entre puntos."""
    if t <= puntos[0][0]:
        return QPointF(puntos[0][1], puntos[0][2])
    for (t0, x0, y0), (t1, x1, y1) in zip(puntos, puntos[1:]):
        if t <= t1:
            k = suave(tramo(t, t0, t1))
            return QPointF(mezcla(x0, x1, k), mezcla(y0, y1, k))
    return QPointF(puntos[-1][1], puntos[-1][2])


def entra_sale(t, a, b, fundido=0.25):
    """Opacidad de algo que aparece en a y desaparece en b."""
    return min(salida(tramo(t, a, a + fundido)), 1 - tramo(t, b - fundido, b))


def lienzo():
    img = QImage(int(W * ESCALA), int(H * ESCALA), QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(ESCALA)
    return img


def pintor(img):
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    return p


def capa(widget, con_fondo=False):
    """El widget de Orbit, renderizado nítido a la escala del video."""
    img = QImage(round(widget.width() * ESCALA), round(widget.height() * ESCALA), QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(ESCALA)
    img.fill(Qt.transparent)
    p = QPainter(img)
    banderas = QWidget.RenderFlag.DrawChildren
    if con_fondo:
        banderas |= QWidget.RenderFlag.DrawWindowBackground
    widget.render(p, QPoint(0, 0), QRegion(), banderas)
    p.end()
    return img


def preparar(widget):
    """Lo muestra fuera de la pantalla para que Qt calcule su diseño, sin que aparezca."""
    widget.setAttribute(Qt.WA_DontShowOnScreen)
    widget.show()
    app.processEvents()
    return widget


def vidrio(base, x, y, ancho, alto):
    """El fondo desenfocado que las piezas de Orbit ponen detrás de sí (como al capturar la pantalla)."""
    recorte = base.copy(round(x * ESCALA), round(y * ESCALA), round(ancho * ESCALA), round(alto * ESCALA))
    recorte = estilo.desenfocar(recorte)
    recorte.setDevicePixelRatio(ESCALA)
    return QPixmap.fromImage(recorte)


def fuente(tam, peso=QFont.Normal, titulo=False):
    return estilo.fuente(tam, peso, titulo)


def texto(p, rect, cadena, tam, color, peso=QFont.Normal, alineado=Qt.AlignLeft | Qt.AlignVCenter, titulo=False):
    p.setFont(fuente(tam, peso, titulo))
    p.setPen(QColor(color))
    p.drawText(rect, alineado, cadena)


# ---------------------------------------------------------------- escenario: escritorio, barra y ventanas

def _fondo_escritorio():
    img = lienzo()
    p = pintor(img)
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0, QColor("#0b1638"))
    g.setColorAt(1, QColor("#04060f"))
    p.fillRect(QRectF(0, 0, W, H), g)
    # "Bloom" estilo Windows 11: pétalos de luz azul y violeta
    centro = QPointF(W * 0.56, H * 0.56)
    for angulo, largo, color in ((-35, 520, "#2d6bff"), (10, 470, "#4a8bff"), (55, 420, "#7a5cff"),
                                 (100, 380, "#2bb3ff"), (150, 430, "#3a5cff"), (-80, 360, "#5f7dff")):
        p.save()
        p.translate(centro)
        p.rotate(angulo)
        rg = QRadialGradient(QPointF(largo * 0.45, 0), largo * 0.55)
        c = QColor(color)
        c.setAlpha(150)
        rg.setColorAt(0, c)
        c.setAlpha(0)
        rg.setColorAt(1, c)
        p.setPen(Qt.NoPen)
        p.setBrush(rg)
        p.drawEllipse(QRectF(0, -largo * 0.22, largo, largo * 0.44))
        p.restore()
    brillo = QRadialGradient(centro, 160)
    brillo.setColorAt(0, QColor(170, 205, 255, 120))
    brillo.setColorAt(1, QColor(170, 205, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(brillo)
    p.drawEllipse(centro, 160, 160)
    vineta = QRadialGradient(QPointF(W / 2, H / 2), W * 0.75)
    vineta.setColorAt(0.6, QColor(0, 0, 0, 0))
    vineta.setColorAt(1, QColor(0, 0, 0, 150))
    p.fillRect(QRectF(0, 0, W, H), vineta)
    p.end()
    return img


FONDO = _fondo_escritorio()
FONDO_BARRA = vidrio(FONDO, 0, H - BARRA, W, BARRA)


def escritorio(p):
    p.drawImage(QPointF(0, 0), FONDO)


def logo_mini(p, rect):
    estilo.dibujar_logo(p, rect)


def barra_de_tareas(p, resaltar_orbit=0.0):
    caja = QRectF(0, H - BARRA, W, BARRA)
    p.drawPixmap(caja.topLeft(), FONDO_BARRA)
    p.fillRect(caja, QColor(26, 26, 30, 205))
    p.setPen(QPen(QColor(255, 255, 255, 22), 1))
    p.drawLine(QPointF(0, H - BARRA + 0.5), QPointF(W, H - BARRA + 0.5))
    y = H - BARRA / 2
    # Inicio, buscador y algunas apps, centrados
    x = W / 2 - 150
    p.setPen(Qt.NoPen)
    for dx, dy in ((0, 0), (9, 0), (0, 9), (9, 9)):
        p.setBrush(QColor("#4cc2ff"))
        p.drawRoundedRect(QRectF(x + dx - 8, y + dy - 8, 7.5, 7.5), 1.5, 1.5)
    x += 34
    p.setBrush(QColor(255, 255, 255, 22))
    p.setPen(QPen(QColor(255, 255, 255, 25), 1))
    p.drawRoundedRect(QRectF(x - 6, y - 15, 150, 30), 15, 15)
    p.setPen(QPen(QColor(255, 255, 255, 170), 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(x + 9, y - 1.5), 5, 5)
    p.drawLine(QPointF(x + 12.5, y + 2), QPointF(x + 16, y + 5.5))
    texto(p, QRectF(x + 24, y - 15, 110, 30), "Buscar", 9, "#c8c8cc")
    x += 172
    for color in ("#f7c948", "#2f7bff", "#30d158", "#bf5af2"):
        p.setPen(Qt.NoPen)
        g = QLinearGradient(x - 11, y - 11, x + 11, y + 11)
        g.setColorAt(0, QColor(color).lighter(125))
        g.setColorAt(1, QColor(color))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(x - 11, y - 11, 22, 22), 6, 6)
        x += 40
    # Bandeja: flecha, Orbit, wifi, sonido, batería y reloj
    p.setPen(QPen(QColor(255, 255, 255, 190), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(1096, y + 2), QPointF(1100, y - 2), QPointF(1104, y + 2)]))
    if resaltar_orbit > 0:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, int(28 * resaltar_orbit)))
        p.drawRoundedRect(QRectF(BANDEJA.x() - 16, y - 18, 32, 36), 6, 6)
    logo_mini(p, QRectF(BANDEJA.x() - 9, y - 9, 18, 18))
    p.setPen(QPen(QColor(255, 255, 255, 220), 1.5, Qt.SolidLine, Qt.RoundCap))
    for r in (3, 6.5, 10):
        p.drawArc(QRectF(1162 - r, y + 4 - r, 2 * r, 2 * r), 50 * 16, 80 * 16)
    p.drawLine(QPointF(1180, y - 2), QPointF(1180, y + 2))
    p.drawPolyline(QPolygonF([QPointF(1180, y - 2), QPointF(1184, y - 5), QPointF(1184, y + 5), QPointF(1180, y + 2)]))
    p.drawArc(QRectF(1184, y - 4, 6, 8), -60 * 16, 120 * 16)
    texto(p, QRectF(1196, y - 16, 76, 16), "10:24", 8.5, "#f0f0f2", alineado=Qt.AlignRight | Qt.AlignVCenter)
    texto(p, QRectF(1196, y, 76, 16), "24/10/2026", 8.5, "#f0f0f2", alineado=Qt.AlignRight | Qt.AlignVCenter)


def sombra(p, caja, radio=8, fuerza=1.0):
    p.setPen(Qt.NoPen)
    for i in range(14, 0, -2):
        p.setBrush(QColor(0, 0, 0, int(7 * fuerza * (1 - i / 14) ** 1.3 * 3)))
        p.drawRoundedRect(caja.adjusted(-i, -i + 6, i, i + 6), radio + i, radio + i)


def ventana(p, caja, titulo, icono_color="#4cc2ff", activa=True):
    """Marco de ventana de Windows 11 (modo oscuro). Devuelve el área del contenido."""
    sombra(p, caja)
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.setBrush(QColor("#202022"))
    p.drawRoundedRect(caja, 8, 8)
    barra = QRectF(caja.left(), caja.top(), caja.width(), 34)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(icono_color))
    p.drawRoundedRect(QRectF(barra.left() + 14, barra.center().y() - 7, 14, 14), 3.5, 3.5)
    texto(p, QRectF(barra.left() + 38, barra.top(), 400, barra.height()), titulo, 9,
          "#f0f0f2" if activa else "#9a9a9f")
    p.setPen(QPen(QColor(255, 255, 255, 200), 1.1))
    cx = barra.right() - 23
    p.drawLine(QPointF(cx - 5, barra.center().y() - 5), QPointF(cx + 5, barra.center().y() + 5))
    p.drawLine(QPointF(cx + 5, barra.center().y() - 5), QPointF(cx - 5, barra.center().y() + 5))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(cx - 50, barra.center().y() - 5, 10, 10))
    p.drawLine(QPointF(cx - 95, barra.center().y()), QPointF(cx - 85, barra.center().y()))
    return QRectF(caja.left() + 1, caja.top() + 34, caja.width() - 2, caja.height() - 35)


def icono_archivo(p, caja, tipo):
    p.save()
    p.setPen(Qt.NoPen)
    if tipo == "carpeta":
        p.setBrush(QColor("#e8a92b"))
        p.drawRoundedRect(QRectF(caja.left(), caja.top() + 2, caja.width() * 0.45, 5), 1.5, 1.5)
        p.setBrush(QColor("#f7c948"))
        p.drawRoundedRect(QRectF(caja.left(), caja.top() + 4, caja.width(), caja.height() - 6), 2, 2)
    else:
        color, letra = {"docx": ("#2b6fdc", "W"), "xlsx": ("#1f9d55", "X"), "pdf": ("#e5484d", "PDF"),
                        "png": ("#9b6bff", "")}[tipo]
        hoja = QRectF(caja.left() + 2, caja.top(), caja.width() - 4, caja.height())
        p.setBrush(QColor("#e9eaee"))
        p.drawRoundedRect(hoja, 2, 2)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(hoja.left() - 2, hoja.top() + hoja.height() * 0.38, hoja.width() * 0.78,
                                 hoja.height() * 0.42), 2, 2)
        p.setPen(Qt.white)
        p.setFont(fuente(5.5 if len(letra) > 1 else 7, QFont.Bold))
        p.drawText(QRectF(hoja.left() - 2, hoja.top() + hoja.height() * 0.38, hoja.width() * 0.78,
                          hoja.height() * 0.42), Qt.AlignCenter, letra)
    p.restore()


ARCHIVOS = [("carpeta", "Fotos del viaje", "12/10/2026 18:40", "Carpeta de archivos", ""),
            ("docx", "Informe final.docx", "23/10/2026 21:15", "Documento de Word", "284 KB"),
            ("xlsx", "Presupuesto.xlsx", "20/10/2026 09:02", "Hoja de Excel", "36 KB"),
            ("pdf", "Apuntes de física.pdf", "18/10/2026 16:27", "Documento PDF", "1,2 MB"),
            ("png", "Captura.png", "17/10/2026 11:58", "Imagen PNG", "412 KB")]
NUEVO_PDF = ("pdf", "Informe final.pdf", "24/10/2026 10:24", "Documento PDF", "198 KB")
CAJA_EXPLORADOR = QRectF(330, 178, 800, 470)
FILA_EXPLORADOR = 34


def explorador(p, elegido=-1, nuevo=0.0):
    area = ventana(p, CAJA_EXPLORADOR, "Documentos", "#f7c948")
    # barra de herramientas y lateral
    p.fillRect(QRectF(area.left(), area.top(), area.width(), 40), QColor("#1b1b1d"))
    for i, nombre in enumerate(("Nuevo", "Cortar", "Copiar", "Pegar", "Ordenar", "Ver")):
        texto(p, QRectF(area.left() + 16 + i * 74, area.top(), 70, 40), nombre, 8.5, "#c8c8cc")
    lateral = QRectF(area.left(), area.top() + 40, 170, area.height() - 40)
    p.fillRect(lateral, QColor("#1c1c1e"))
    for i, nombre in enumerate(("Inicio", "Galería", "Escritorio", "Descargas", "Documentos", "Imágenes", "Música")):
        fila = QRectF(lateral.left() + 8, lateral.top() + 12 + i * 32, lateral.width() - 16, 28)
        if nombre == "Documentos":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 22))
            p.drawRoundedRect(fila, 5, 5)
        icono_archivo(p, QRectF(fila.left() + 10, fila.top() + 7, 15, 13), "carpeta")
        texto(p, fila.adjusted(34, 0, 0, 0), nombre, 9, "#e6e6ea")
    lista = QRectF(lateral.right() + 8, area.top() + 48, area.right() - lateral.right() - 16, area.height() - 56)
    columnas = (("Nombre", 0), ("Fecha de modificación", 250), ("Tipo", 420), ("Tamaño", 540))
    for nombre, x in columnas:
        texto(p, QRectF(lista.left() + 12 + x, lista.top(), 200, 26), nombre, 8.5, "#9a9a9f")
    p.setPen(QPen(QColor(255, 255, 255, 18), 1))
    p.drawLine(QPointF(lista.left(), lista.top() + 28), QPointF(lista.right(), lista.top() + 28))
    filas = ARCHIVOS + ([NUEVO_PDF] if nuevo > 0 else [])
    for i, (tipo, nombre, fecha, clase, tam) in enumerate(filas):
        fila = QRectF(lista.left(), lista.top() + 32 + i * FILA_EXPLORADOR, lista.width(), FILA_EXPLORADOR - 2)
        p.save()
        if i == len(ARCHIVOS):  # el PDF recién creado aparece con un brillo
            p.setOpacity(salida(min(1.0, nuevo * 2)))
            p.setPen(Qt.NoPen)
            acento = QColor(estilo.paleta().acento)
            acento.setAlpha(int(70 * (1 - tramo(nuevo, 0.5, 1.0)) + 35))
            p.setBrush(acento)
            p.drawRoundedRect(fila, 5, 5)
        elif i == elegido:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 26))
            p.drawRoundedRect(fila, 5, 5)
        icono_archivo(p, QRectF(fila.left() + 12, fila.top() + 7, 16, 19), tipo)
        valores = (nombre, fecha, clase, tam)
        for (_, x), valor in zip(columnas, valores):
            texto(p, QRectF(fila.left() + 12 + x + (26 if x == 0 else 0), fila.top(), 240, fila.height()), valor, 9,
                  "#f0f0f2" if x == 0 else "#b4b4ba")
        p.restore()


def fila_explorador(i):
    area_top = CAJA_EXPLORADOR.top() + 34
    lista_left = CAJA_EXPLORADOR.left() + 1 + 170 + 8
    return QRectF(lista_left, area_top + 48 + 32 + i * FILA_EXPLORADOR, 600, FILA_EXPLORADOR - 2)


# ---------------------------------------------------------------- cursor, clics, títulos y teclas

def cursor(p, pos, presion=0.0):
    p.save()
    p.translate(pos)
    p.scale(1.15 - 0.12 * presion, 1.15 - 0.12 * presion)
    flecha = QPolygonF([QPointF(0, 0), QPointF(0, 17), QPointF(4.2, 13), QPointF(7.2, 19.6), QPointF(10, 18.4),
                        QPointF(7.1, 12), QPointF(12.6, 12)])
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 70))
    p.drawPolygon(flecha.translated(1, 1.5))
    p.setPen(QPen(QColor("#111"), 1.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.white)
    p.drawPolygon(flecha)
    p.restore()


def onda(p, pos, k):
    """Anillo que se expande al hacer clic, para que se note en el video."""
    if not 0 < k < 1:
        return
    color = QColor(estilo.paleta().acento)
    color.setAlphaF(0.75 * (1 - k))
    p.setPen(QPen(color, 2.5))
    p.setBrush(Qt.NoBrush)
    r = 6 + 20 * salida(k)
    p.drawEllipse(pos, r, r)


def clic(p, pos, t, momento):
    onda(p, pos, tramo(t, momento, momento + 0.45))
    presion = 1 - abs(tramo(t, momento - 0.08, momento + 0.08) * 2 - 1) if momento - 0.08 < t < momento + 0.08 else 0
    return presion


def titulo(p, t, principal, secundario, aparece=0.0, desaparece=99.0):
    k = entra_sale(t, aparece, desaparece, 0.35)
    if k <= 0:
        return
    p.save()
    fondo = QRadialGradient(QPointF(0, 0), 560)
    fondo.setColorAt(0, QColor(0, 0, 0, 150))
    fondo.setColorAt(1, QColor(0, 0, 0, 0))
    p.setOpacity(k)
    p.fillRect(QRectF(0, 0, W, H), fondo)
    p.translate(0, 10 * (1 - salida(tramo(t, aparece, aparece + 0.45))))
    p.setPen(QColor(0, 0, 0, 90))
    p.setFont(fuente(25, QFont.DemiBold, titulo=True))
    p.drawText(QRectF(56, 41, 900, 46), Qt.AlignLeft | Qt.AlignVCenter, principal)
    p.setPen(Qt.white)
    p.drawText(QRectF(56, 40, 900, 46), Qt.AlignLeft | Qt.AlignVCenter, principal)
    texto(p, QRectF(58, 86, 900, 26), secundario, 12.5, QColor(255, 255, 255, 205))
    p.restore()


def teclas(p, t, nombres, aparece, presiona, desaparece=99.0, x=58, y=126):
    k = entra_sale(t, aparece, desaparece, 0.25)
    if k <= 0:
        return
    p.save()
    p.setOpacity(k)
    hundida = presiona <= t < presiona + 0.35
    p.setFont(fuente(10, QFont.DemiBold))
    metricas = QFontMetricsF(p.font())
    for i, nombre in enumerate(nombres):
        ancho = max(34, metricas.horizontalAdvance(nombre) + 22)
        dy = 2 if hundida else 0
        caja = QRectF(x, y + dy, ancho, 32)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(caja.translated(0, 3 - dy), 7, 7)
        p.setPen(QPen(QColor(255, 255, 255, 80), 1))
        p.setBrush(QColor(255, 255, 255, 70 if hundida else 34))
        p.drawRoundedRect(caja, 7, 7)
        p.setPen(Qt.white)
        p.drawText(caja, Qt.AlignCenter, nombre)
        x += ancho + 8
    p.restore()


def dibujar(p, img, pos, opacidad=1.0, escala=1.0):
    if opacidad <= 0:
        return
    p.save()
    p.setOpacity(opacidad)
    if escala != 1.0:
        centro = QPointF(pos.x() + img.width() / ESCALA / 2, pos.y() + img.height() / ESCALA / 2)
        p.translate(centro)
        p.scale(escala, escala)
        p.translate(-centro)
    p.drawImage(pos, img)
    p.restore()


# ---------------------------------------------------------------- app de mentira para crear las piezas de Orbit

class AppDemo(QObject):
    """Lo mínimo que piden el panel, los ajustes y los plugins, sin arrancar Orbit de verdad
    (no registra atajos, no escucha el portapapeles ni toca la Orbit instalada)."""
    cambio = Signal()

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.config.datos = copy.deepcopy(modulo_config.DEFECTO)
        self.config.guardar = lambda: None
        self.aviso = estilo.Aviso()
        self.atajo_ok, self.atajos, self.ventana_ajustes = {}, None, None
        self.plugins = [clase(self) for clase in CLASES]
        for plugin in self.plugins:
            plugin.cfg["instalado"] = True
        for clave, activo in (("radial", True), ("fps", False), ("despierto", False), ("pomodoro", False)):
            self.config.plugin(clave)["activo"] = activo
        self.plugin("audio").estado = lambda: "Ctrl + Alt + Shift + A"

    def plugin(self, clave):
        return next(p for p in self.plugins if p.id == clave)

    def __getattr__(self, nombre):  # fijar_activo, salir, abrir_ajustes...: no hacen nada en el video
        return lambda *a, **k: None


demo = AppDemo()


def aviso(p, t, tipo, principal, detalle, aparece, dura=1.6, color=None):
    """El aviso flotante real de Orbit (abajo en el centro)."""
    k = tramo(t, aparece, aparece + 0.26)
    k = salida(k) * (1 - tramo(t, aparece + dura, aparece + dura + 0.26))
    if k <= 0:
        return
    hud = demo.aviso
    hud.tipo, hud.titulo, hud.detalle = tipo, principal, detalle
    hud.color = QColor(color) if color else None
    hud._t = k
    ancho = max(220, 90 + 9 * max(len(principal), len(detalle)))
    hud.resize(ancho, 64)
    dibujar(p, capa(hud), QPointF(W / 2 - ancho / 2, H - BARRA - 140), k)


# ---------------------------------------------------------------- escenas

class Escena:
    duracion = 4.0

    def pintar(self, p, t):
        raise NotImplementedError


def fondo_oscuro(p, t):
    g = QRadialGradient(QPointF(W / 2, H * 0.42), W * 0.7)
    g.setColorAt(0, QColor("#16204a"))
    g.setColorAt(1, QColor("#05060c"))
    p.fillRect(QRectF(0, 0, W, H), g)
    p.save()
    p.translate(W / 2, H * 0.42)
    for i, (rx, ry, vel) in enumerate(((360, 120, 6), (480, 165, -4), (600, 210, 3))):
        p.save()
        p.rotate(-18 + t * vel)
        p.setPen(QPen(QColor(120, 150, 255, 26 - i * 5), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), rx, ry)
        angulo = t * (0.6 - i * 0.15) + i * 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(150, 180, 255, 70))
        p.drawEllipse(QPointF(rx * math.cos(angulo), ry * math.sin(angulo)), 3, 3)
        p.restore()
    p.restore()


class Intro(Escena):
    duracion = 3.2

    def pintar(self, p, t):
        fondo_oscuro(p, t)
        k = tramo(t, 0.1, 0.9)
        tam = 132 * rebote(k, 1.4)
        if tam > 1:
            p.save()
            p.setOpacity(tramo(t, 0.1, 0.4))
            estilo.dibujar_logo(p, QRectF(W / 2 - tam / 2, 250 - tam / 2, tam, tam))
            p.restore()
        p.save()
        p.setOpacity(salida(tramo(t, 0.55, 1.1)))
        p.translate(0, 14 * (1 - salida(tramo(t, 0.55, 1.1))))
        texto(p, QRectF(0, 335, W, 70), "Orbit", 40, "#ffffff", QFont.DemiBold, Qt.AlignCenter, titulo=True)
        p.restore()
        p.save()
        p.setOpacity(salida(tramo(t, 0.9, 1.5)))
        texto(p, QRectF(0, 405, W, 30), "Pequeñas herramientas que viven junto al reloj de Windows", 14,
              QColor(255, 255, 255, 200), alineado=Qt.AlignCenter)
        p.restore()


class EscenaPanel(Escena):
    duracion = 5.0

    def __init__(self):
        self.panel = Panel(demo)
        self.panel.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)  # sin comportamiento de menú emergente
        self.panel.setAttribute(Qt.WA_TranslucentBackground)
        self.panel.refrescar()
        self.panel._ajustar_alto(QRect(0, 0, W, 4000))
        preparar(self.panel)
        self.x = W - self.panel.width() + SOMBRA_PANEL - 10
        self.y = H - BARRA - self.panel.height() + SOMBRA_PANEL - 6
        base = lienzo()
        q = pintor(base)
        escritorio(q)
        barra_de_tareas(q)
        q.end()
        self.panel.fondo = vidrio(base, self.x, self.y, self.panel.width(), self.panel.height())
        self.fila_fps = next(f for f in self.panel.filas if f.plugin.id == "fps")
        esquina = self.fila_fps.interruptor.mapTo(self.panel, QPoint(0, 0))
        self.interruptor = QPointF(self.x + esquina.x() + 21, self.y + esquina.y() + 12)

    def pintar(self, p, t):
        escritorio(p)
        barra_de_tareas(p, resaltar_orbit=tramo(t, 1.0, 1.2))
        titulo(p, t, "Todo a un clic", "Tus plugins viven junto al reloj, cada uno con su interruptor.", 0.15)
        puntos = [(0, 700, 420), (0.35, 700, 420), (1.15, BANDEJA.x() - 4, BANDEJA.y() - 6),
                  (1.9, BANDEJA.x() - 4, BANDEJA.y() - 6), (2.6, self.interruptor.x() - 6, self.interruptor.y() - 4),
                  (5, self.interruptor.x() - 6, self.interruptor.y() - 4)]
        pos = camino(t, puntos)
        k = tramo(t, 1.3, 1.65)
        if k > 0:
            fps = self.fila_fps
            encendido = tramo(t, 2.78, 3.05)
            fps.interruptor._pos = rebote(encendido, 1.1)
            fps.estado.fijar("Activado · Ctrl + Alt + Shift + F" if t > 2.8 else "Desactivado")
            for fila in self.panel.filas:
                zona = QRectF(fila.mapTo(self.panel, QPoint(0, 0)), fila.size().toSizeF()).translated(self.x, self.y)
                fila.encima = t > 1.7 and zona.contains(pos)
            img = capa(self.panel)
            dibujar(p, img, QPointF(self.x, self.y + 12 * (1 - rebote(k, 0.8))), salida(k))
        presion = clic(p, pos, t, 1.25) + clic(p, pos, t, 2.75)
        cursor(p, pos, presion)


class EscenaRueda(Escena):
    duracion = 6.4

    def __init__(self):
        self.rueda = Rueda()
        self.rueda.paleta = estilo.paleta()
        self.rueda.recibio_arrastre = True
        self.rueda.rutas = [r"C:\Users\Demo\Documentos\Informe final.docx"]
        self.rueda.acciones = acciones.acciones_para(self.rueda.rutas)
        self.fila = fila_explorador(1)
        self.agarre = QPointF(self.fila.left() + 70, self.fila.center().y())
        self.centro = QPointF(735, 420)
        self.rueda.move(0, 0)
        base = lienzo()
        q = pintor(base)
        escritorio(q)
        explorador(q)
        barra_de_tareas(q)
        q.end()
        self.rueda.fondo = vidrio(base, self.centro.x() - Rueda.TAM / 2, self.centro.y() - Rueda.TAM / 2,
                                  Rueda.TAM, Rueda.TAM)

    def pintar(self, p, t):
        escritorio(p)
        explorador(p, elegido=1 if 0.9 < t < 4.0 else -1, nuevo=tramo(t, 4.2, 5.4))
        barra_de_tareas(p)
        titulo(p, t, "Arrastra y pulsa Tab", "Convierte a PDF, comprime o extrae sin abrir ningún programa.", 0.15)
        teclas(p, t, ["Tab"], 1.55, 1.8, 3.6)
        pdf = QPointF(self.centro.x(), self.centro.y() - 110)
        puntos = [(0, 1000, 610), (0.2, 1000, 610), (0.95, self.agarre.x(), self.agarre.y()),
                  (1.1, self.agarre.x(), self.agarre.y()), (1.7, self.centro.x(), self.centro.y()),
                  (2.5, self.centro.x(), self.centro.y()), (3.1, pdf.x(), pdf.y()), (6.4, pdf.x(), pdf.y())]
        pos = camino(t, puntos)
        arrastrando = 1.1 <= t < 3.8
        # La rueda: se abre con rebote al pulsar Tab y la opción PDF se ilumina al pasar por encima
        r = self.rueda
        apertura = tramo(t, 1.85, 2.17)
        if apertura > 0 and t < 4.05:
            r.progreso = rebote(apertura, 1.2)
            dentro = t > 2.95
            r.encima = r.resaltado = 0 if dentro else -1
            r.resaltado_previo = -1
            r.brillo = tramo(t, 2.95, 3.09) if dentro else 1.0
            opacidad = 1 - tramo(t, 3.8, 4.05)
            dibujar(p, capa(r), QPointF(self.centro.x() - Rueda.TAM / 2, self.centro.y() - Rueda.TAM / 2), opacidad)
        if arrastrando:  # el archivo que se arrastra
            p.save()
            p.setOpacity(0.85)
            icono_archivo(p, QRectF(pos.x() + 14, pos.y() + 14, 22, 26), "docx")
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(30, 30, 32, 210))
            p.drawRoundedRect(QRectF(pos.x() + 40, pos.y() + 18, 128, 22), 6, 6)
            texto(p, QRectF(pos.x() + 48, pos.y() + 18, 120, 22), "Informe final.docx", 8.5, "#ffffff")
            p.restore()
        aviso(p, t, "radial", "Listo", "Informe final.pdf", 4.2, 1.6)
        presion = (1.0 if arrastrando else 0.0) + clic(p, pos, t, 1.05) + clic(p, pos, t, 3.8)
        cursor(p, pos, min(1.0, presion))


class EscenaFPS(Escena):
    duracion = 5.0

    def __init__(self):
        self.medidor = Medidor()
        self.medidor.metricas = {"fps": True, "cpu": True, "gpu": True, "ram": True}
        azar = random.Random(7)
        self.montanas = [[azar.uniform(0.0, 1.0) for _ in range(40)] for _ in range(3)]
        self.lecturas = []
        for i in range(40):
            self.lecturas.append({"fps": 152 + azar.uniform(-9, 8), "cpu_uso": 38 + azar.uniform(-6, 7),
                                  "cpu_temp": 71 + azar.uniform(-1.5, 1.5), "gpu_uso": 93 + azar.uniform(-5, 4),
                                  "gpu_temp": 72 + azar.uniform(-1, 1), "ram_uso": 54 + azar.uniform(-0.4, 0.4),
                                  "ayudante": True})

    def juego(self, p, t):
        cielo = QLinearGradient(0, 0, 0, H * 0.72)
        cielo.setColorAt(0, QColor("#14193f"))
        cielo.setColorAt(0.55, QColor("#5b3b8c"))
        cielo.setColorAt(1, QColor("#ff8a4c"))
        p.fillRect(QRectF(0, 0, W, H), cielo)
        sol = QRadialGradient(QPointF(W * 0.62, H * 0.6), 220)
        sol.setColorAt(0, QColor(255, 220, 160, 255))
        sol.setColorAt(0.18, QColor(255, 190, 120, 230))
        sol.setColorAt(1, QColor(255, 150, 90, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(sol)
        p.drawEllipse(QPointF(W * 0.62, H * 0.6), 220, 220)
        colores = ("#3b2a63", "#2a1e4a", "#170f2c")
        for capa_i, (alturas, color) in enumerate(zip(self.montanas, colores)):
            velocidad = 30 + capa_i * 55
            base = H * (0.62 + capa_i * 0.09)
            paso = 90
            desplazamiento = (t * velocidad) % paso
            indice = int(t * velocidad // paso)
            puntos = [QPointF(-paso, H)]
            for i in range(18):
                altura = alturas[(i + indice) % len(alturas)]
                puntos.append(QPointF(i * paso - desplazamiento, base - altura * (120 - capa_i * 25)))
            puntos.append(QPointF(W + paso, H))
            p.setBrush(QColor(color))
            p.drawPolygon(QPolygonF(puntos))
        # suelo con líneas en perspectiva que avanzan
        suelo = QRectF(0, H * 0.84, W, H * 0.16)
        p.fillRect(suelo, QColor("#0d0820"))
        p.setPen(QPen(QColor(255, 120, 200, 90), 1.2))
        for i in range(8):
            k = ((i + t * 1.6) % 8) / 8
            y = suelo.top() + suelo.height() * k * k
            p.drawLine(QPointF(0, y), QPointF(W, y))
        for i in range(-12, 13):
            p.drawLine(QPointF(W / 2 + i * 30, suelo.top()), QPointF(W / 2 + i * 160, H))

    def pintar(self, p, t):
        self.juego(p, t)
        titulo(p, t, "Medidor FPS", "FPS, CPU, GPU y RAM encima de cualquier juego.", 0.15)
        teclas(p, t, ["Ctrl", "Alt", "Shift", "F"], 0.5, 0.95, 2.4)
        k = tramo(t, 1.05, 1.3)
        if k > 0:
            self.medidor.actualizar(self.lecturas[int(t * 4) % len(self.lecturas)])
            img = capa(self.medidor)
            dibujar(p, img, QPointF(W - self.medidor.width() - 16, 16), salida(k))


class EscenaOCR(Escena):
    duracion = 5.2
    VENTANA = QRectF(300, 172, 740, 486)
    PAGINA = QRectF(340, 222, 660, 400)
    PARRAFO = QRectF(376, 354, 590, 112)

    def __init__(self):
        self.base = lienzo()
        q = pintor(self.base)
        self.escenario(q)
        q.end()
        captura = QPixmap.fromImage(self.base)
        captura.setDevicePixelRatio(ESCALA)
        self.selector = SelectorPantalla("area")
        self.lienzo = _Lienzo(self.selector, QGuiApplication.primaryScreen(), captura)
        self.lienzo.resize(W, H)

    def escenario(self, p):
        escritorio(p)
        area = ventana(p, self.VENTANA, "Clase 7 - Circuitos.pdf", "#e5484d")
        p.fillRect(area, QColor("#3a3a3e"))
        pagina = self.PAGINA
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#fbfbfd"))
        p.drawRect(pagina)
        texto(p, QRectF(pagina.left() + 36, pagina.top() + 26, 500, 20), "UNIDAD 2 · CIRCUITOS ELÉCTRICOS", 8.5,
              "#2b6fdc", QFont.DemiBold)
        texto(p, QRectF(pagina.left() + 36, pagina.top() + 50, 500, 50), "Ley de Ohm", 24, "#16161a", QFont.DemiBold,
              titulo=True)
        parrafo = ("La corriente que circula por un conductor es directamente proporcional al voltaje aplicado e "
                   "inversamente proporcional a su resistencia. Se cumple en materiales óhmicos a temperatura "
                   "constante, como la mayoría de los metales.")
        p.setFont(fuente(11.5))
        p.setPen(QColor("#2c2c33"))
        p.drawText(self.PARRAFO.adjusted(4, 4, -4, -4), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, parrafo)
        formula = QRectF(pagina.left() + 36, pagina.top() + 262, 230, 64)
        p.setBrush(QColor("#eef3ff"))
        p.drawRoundedRect(formula, 10, 10)
        texto(p, formula, "V = I · R", 22, "#1d4fd7", QFont.DemiBold, Qt.AlignCenter, titulo=True)
        texto(p, QRectF(pagina.left() + 290, pagina.top() + 262, 330, 64),
              "V: voltaje (V)   I: corriente (A)   R: resistencia (Ω)", 9.5, "#55555e")
        barra_de_tareas(p)

    def pintar(self, p, t):
        p.drawImage(QPointF(0, 0), self.base)
        inicio = QPointF(self.PARRAFO.left(), self.PARRAFO.top())
        fin = QPointF(self.PARRAFO.right(), self.PARRAFO.bottom())
        puntos = [(0, 700, 560), (0.3, 700, 560), (1.25, inicio.x(), inicio.y()), (1.45, inicio.x(), inicio.y()),
                  (2.45, fin.x(), fin.y()), (5.2, fin.x(), fin.y())]
        pos = camino(t, puntos)
        k = tramo(t, 1.0, 1.15) * (1 - tramo(t, 2.65, 2.8))
        if k > 0:
            self.lienzo.inicio = inicio if t > 1.45 else None
            self.lienzo.fin = pos if t > 1.45 else None
            dibujar(p, capa(self.lienzo), QPointF(0, 0), k)
        titulo(p, t, "Texto de pantalla", "Copia el texto de una imagen, un video o un PDF escaneado.", 0.15)
        teclas(p, t, ["Ctrl", "Alt", "Shift", "T"], 0.5, 0.9, 2.2)
        aviso(p, t, "ocr", "Texto copiado", "38 palabras", 2.85, 1.7)
        presion = (1.0 if 1.45 <= t < 2.65 else 0.0) + clic(p, pos, t, 1.45)
        cursor(p, pos, min(1.0, presion))


def _png(ancho, alto, dibujo):
    img = QImage(ancho, alto, QImage.Format_ARGB32)
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    dibujo(q, ancho, alto)
    q.end()
    datos = QByteArray()
    buffer = QBuffer(datos)
    buffer.open(QIODevice.WriteOnly)
    img.save(buffer, "PNG")
    return bytes(datos)


def _foto(q, ancho, alto):
    g = QLinearGradient(0, 0, ancho, alto)
    g.setColorAt(0, QColor("#ff9f0a"))
    g.setColorAt(1, QColor("#bf5af2"))
    q.fillRect(0, 0, ancho, alto, g)
    q.setPen(Qt.NoPen)
    q.setBrush(QColor(255, 255, 255, 170))
    q.drawEllipse(QPointF(ancho * 0.7, alto * 0.35), alto * 0.18, alto * 0.18)
    q.setBrush(QColor(20, 10, 40, 180))
    q.drawPolygon(QPolygonF([QPointF(0, alto), QPointF(ancho * 0.35, alto * 0.45), QPointF(ancho * 0.6, alto),
                             QPointF(ancho * 0.75, alto * 0.6), QPointF(ancho, alto)]))


class EscenaPortapapeles(Escena):
    duracion = 5.2
    NOTAS = QRectF(330, 172, 720, 470)
    CARET = QPointF(363, 329)
    PEGADO = "Reunión del proyecto: jueves 18:00 en la biblioteca"

    def __init__(self):
        ahora = time.time()
        historial = Historial()
        elementos = [Historial.texto("#0A84FF", "c5", ahora - 2400),
                     Historial.imagen(_png(640, 400, _foto), _png(96, 60, _foto), 640, 400, "c4", ahora - 1500),
                     Historial.texto(self.PEGADO, "c3", ahora - 720),
                     Historial.texto("https://github.com/Abrahamdlt/Orbit", "c2", ahora - 300),
                     Historial.texto("La corriente que circula por un conductor es directamente proporcional al "
                                     "voltaje aplicado…", "c1", ahora - 60)]
        for elemento in elementos:
            historial.agregar(elemento)
        self.lista = Lista(historial)
        self.lista.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.lista.setAttribute(Qt.WA_TranslucentBackground)
        self.lista._filtrar("")
        from orbit.plugins.portapapeles.lista import ALTO_FILA, FILAS_VISIBLES
        self.lista.desplazable.setFixedHeight(min(len(self.lista.visibles), FILAS_VISIBLES) * ALTO_FILA)
        self.lista.adjustSize()
        preparar(self.lista)
        self.x = self.CARET.x() - SOMBRA_LISTA - 24 + 40
        self.y = self.CARET.y() + 14 - SOMBRA_LISTA
        base = lienzo()
        q = pintor(base)
        self.escenario(q, 0)
        q.end()
        self.lista.fondo = vidrio(base, self.x, self.y, self.lista.width(), self.lista.height())

    def escenario(self, p, pegado):
        escritorio(p)
        area = ventana(p, self.NOTAS, "Notas.txt - Bloc de notas", "#4cc2ff")
        p.fillRect(QRectF(area.left(), area.top(), area.width(), 30), QColor("#1b1b1d"))
        for i, nombre in enumerate(("Archivo", "Editar", "Ver")):
            texto(p, QRectF(area.left() + 14 + i * 64, area.top(), 60, 30), nombre, 9, "#c8c8cc")
        lineas = ["Apuntes de la semana", "- Repasar la Ley de Ohm (diapositiva 7)", "- Pendientes del proyecto:"]
        y = area.top() + 44
        for linea in lineas:
            texto(p, QRectF(area.left() + 30, y, 640, 24), linea, 11, "#e8e8ec")
            y += 26
        if pegado > 0:
            p.save()
            fondo = QColor(estilo.paleta().acento)
            fondo.setAlpha(int(90 * (1 - tramo(pegado, 0.3, 1.0))))
            p.fillRect(QRectF(area.left() + 28, y, 470, 24), fondo)
            texto(p, QRectF(area.left() + 30, y, 640, 24), "  " + self.PEGADO, 11, "#e8e8ec")
            p.restore()
        barra_de_tareas(p)

    def pintar(self, p, t):
        self.escenario(p, tramo(t, 2.95, 4.2))
        if int(t * 2) % 2 == 0 and t < 2.9:  # cursor de texto parpadeando
            p.fillRect(QRectF(self.CARET.x(), self.CARET.y() - 1, 1.5, 22), QColor("#e8e8ec"))
        titulo(p, t, "Historial del portapapeles", "Todo lo que copiaste, con buscador. Eliges y se pega.", 0.15)
        teclas(p, t, ["Ctrl", "Alt", "Shift", "V"], 0.5, 0.9, 1.5)
        teclas(p, t, ["↓"], 1.55, 1.75, 2.35)
        teclas(p, t, ["↓"], 1.95, 2.15, 2.35, x=104)
        teclas(p, t, ["Enter"], 2.45, 2.65, 3.4)
        k = tramo(t, 1.0, 1.25) * (1 - tramo(t, 2.75, 2.9))
        if k > 0:
            self.lista.seleccionar(0 if t < 1.75 else 1 if t < 2.15 else 2, desplazar=False)
            dibujar(p, capa(self.lista), QPointF(self.x, self.y + 8 * (1 - rebote(tramo(t, 1.0, 1.3), 0.8))), salida(k))


class EscenaColor(Escena):
    duracion = 4.4
    MUESTRAS = ["#0A84FF", "#30D158", "#FF9F0A", "#FF375F", "#BF5AF2", "#64D2FF"]
    VENTANA = QRectF(330, 172, 840, 480)

    def __init__(self):
        self.base = lienzo()
        q = pintor(self.base)
        self.escenario(q)
        q.end()
        captura = QPixmap.fromImage(self.base)
        captura.setDevicePixelRatio(ESCALA)
        self.selector = SelectorPantalla("punto")
        self.lienzo = _Lienzo(self.selector, QGuiApplication.primaryScreen(), captura)
        self.lienzo.resize(W, H)

    def caja_muestra(self, i):
        return QRectF(self.VENTANA.left() + 505 + (i % 2) * 112, self.VENTANA.top() + 100 + (i // 2) * 120, 92, 92)

    def escenario(self, p):
        escritorio(p)
        area = ventana(p, self.VENTANA, "Paleta - Proyecto Orbit", "#bf5af2")
        arte = QRectF(area.left() + 24, area.top() + 24, 430, area.height() - 48)
        g = QLinearGradient(arte.topLeft(), arte.bottomRight())
        g.setColorAt(0, QColor("#0A84FF"))
        g.setColorAt(0.5, QColor("#BF5AF2"))
        g.setColorAt(1, QColor("#FF375F"))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(arte, 14, 14)
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawEllipse(QPointF(arte.center().x() + 60, arte.center().y() - 50), 90, 90)
        texto(p, QRectF(area.left() + 504, area.top() + 24, 300, 24), "Colores del proyecto", 11, "#f0f0f2",
              QFont.DemiBold)
        for i, color in enumerate(self.MUESTRAS):
            caja = self.caja_muestra(i)
            p.setBrush(QColor(color))
            p.drawRoundedRect(caja, 14, 14)
        barra_de_tareas(p)

    def pintar(self, p, t):
        p.drawImage(QPointF(0, 0), self.base)
        destino = self.caja_muestra(0).center()
        puntos = [(0, 900, 640), (0.3, 900, 640), (0.8, 520, 470), (1.4, 640, 330), (2.25, destino.x(), destino.y()),
                  (4.4, destino.x(), destino.y())]
        pos = camino(t, puntos)
        k = tramo(t, 0.85, 1.0) * (1 - tramo(t, 2.45, 2.6))
        if k > 0:
            self.lienzo.raton = QPoint(int(pos.x() * ESCALA), int(pos.y() * ESCALA))
            dibujar(p, capa(self.lienzo), QPointF(0, 0), k)
        titulo(p, t, "Cuentagotas", "Copia el color de cualquier píxel en HEX, RGB o HSL.", 0.15)
        teclas(p, t, ["Ctrl", "Alt", "Shift", "C"], 0.4, 0.75, 2.0)
        aviso(p, t, "color", "#0A84FF", "Copiado", 2.6, 1.5, color="#0A84FF")
        if not 0.95 < t < 2.5:  # con la lupa abierta el cursor se oculta
            cursor(p, pos, clic(p, pos, t, 2.45))
        else:
            clic(p, pos, t, 2.45)


class EscenaMas(Escena):
    duracion = 6.0
    REPRODUCTOR = QRectF(380, 190, 560, 360)
    TEXTOS = [("Siempre encima", "Fija una ventana por encima de las demás.", ["P"]),
              ("Pomodoro", "Enfoque y descansos sin perder la cuenta.", ["O"]),
              ("Cambio de audio", "De audífonos a parlantes con un atajo.", ["A"]),
              ("Mantener despierto", "Que el equipo no se suspenda mientras descargas.", ["D"])]

    def __init__(self):
        self.temporizador = Temporizador()
        self.pastilla = PastillaPomodoro(self.temporizador)

    def reproductor(self, p, t):
        area = ventana(p, self.REPRODUCTOR, "Clase 7 - Circuitos.mp4", "#ff9f0a")
        g = QLinearGradient(area.topLeft(), area.bottomRight())
        g.setColorAt(0, QColor("#1d2b52"))
        g.setColorAt(1, QColor("#0e1324"))
        p.fillRect(area, g)
        texto(p, area.adjusted(0, -30, 0, -30), "V = I · R", 30, QColor(255, 255, 255, 220), QFont.DemiBold,
              Qt.AlignCenter, titulo=True)
        barra = QRectF(area.left() + 20, area.bottom() - 26, area.width() - 40, 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawRoundedRect(barra, 2, 2)
        avance = 0.32 + t * 0.01
        p.setBrush(QColor("#ff453a"))
        p.drawRoundedRect(QRectF(barra.left(), barra.top(), barra.width() * avance, 4), 2, 2)
        p.setBrush(Qt.white)
        p.drawEllipse(QPointF(barra.left() + barra.width() * avance, barra.center().y()), 6, 6)

    def pintar(self, p, t):
        escritorio(p)
        self.reproductor(p, t)
        barra_de_tareas(p)
        # Borde de Siempre encima, como el del plugin
        k = tramo(t, 0.6, 0.85)
        if k > 0:
            p.setPen(QPen(QColor(estilo.paleta().acento), 2.5))
            p.setBrush(Qt.NoBrush)
            p.setOpacity(k)
            p.drawRoundedRect(self.REPRODUCTOR.adjusted(-4, -4, 4, 4), 12, 12)
            p.setOpacity(1)
        # Pastilla del Pomodoro
        k = tramo(t, 2.0, 2.25)
        if k > 0:
            transcurrido = max(0.0, t - 2.0)
            self.temporizador.fase, self.temporizador.corriendo = "enfoque", True
            self.temporizador.enfoques = 1
            self.temporizador.restante = 25 * 60 - 1 - int(transcurrido)
            self.pastilla.resize(int(self.pastilla.ancho_contenido()), 42)
            dibujar(p, capa(self.pastilla), QPointF(W - self.pastilla.width() - 16, H - BARRA - 34 - 8 - 16),
                    salida(k))
        tramo_actual = min(3, int(t / 1.5))
        principal, secundario, letra = self.TEXTOS[tramo_actual]
        inicio = tramo_actual * 1.5
        titulo(p, t, principal, secundario, inicio + (0.0 if tramo_actual == 0 else 0.05),
               inicio + 1.5 if tramo_actual < 3 else 99)
        teclas(p, t, ["Ctrl", "Alt", "Shift"] + letra, inicio + 0.15, inicio + 0.45, inicio + 1.4)
        aviso(p, t, "encima", "Siempre encima", "Ventana fijada", 0.65, 0.75)
        aviso(p, t, "audio", "Audífonos", "Salida de audio", 3.6, 0.85)
        aviso(p, t, "despierto", "Mantener despierto", "Activado · 1 h", 5.1, 1.2)


class EscenaAjustes(Escena):
    duracion = 5.2

    def __init__(self):
        self.ventana = VentanaAjustes(demo)
        self.ventana.resize(860, 500)
        preparar(self.ventana)
        self.x, self.y = W - 860 - 40, 134
        self.indices = {clave: i for i, clave in enumerate(self.ventana.claves)}
        lateral = self.ventana.lateral

        def punto(clave):
            return QPointF(self.x + 110, self.y + 34 + lateral.arriba + self.indices[clave] * 36 + 18)

        self.punto = punto

    def pintar(self, p, t):
        escritorio(p)
        barra_de_tareas(p)
        fps, pomodoro = self.indices["fps"], self.indices["pomodoro"]
        movida1, movida2 = tramo(t, 1.6, 1.9), tramo(t, 3.2, 3.6)
        lateral = self.ventana.lateral
        lateral._y = mezcla(0, fps, suave(movida1)) if t < 3.2 else mezcla(fps, pomodoro, suave(movida2))
        actual = 0 if t < 1.68 else fps if t < 3.38 else pomodoro
        if self.ventana.paginas.currentIndex() != actual:
            self.ventana.paginas.setCurrentIndex(actual)
            lateral.indice = actual
        k = tramo(t, 0.15, 0.55)
        caja = QRectF(self.x, self.y, 860, 500 + 34)
        p.save()
        p.setOpacity(salida(k))
        escala = 0.96 + 0.04 * rebote(k, 0.6)
        p.translate(caja.center())
        p.scale(escala, escala)
        p.translate(-caja.center())
        area = ventana(p, caja, "Ajustes de Orbit", "#7d7aff")
        p.drawImage(QPointF(area.left(), area.top()), capa(self.ventana, con_fondo=True))
        p.restore()
        titulo(p, t, "Cada plugin, a tu manera", "Atajos, opciones y modo bajo consumo en un solo lugar.", 0.2,
               4.0)
        puntos = [(0, 1000, 600), (0.7, 1000, 600), (1.45, self.punto("fps").x(), self.punto("fps").y()),
                  (2.5, self.punto("fps").x(), self.punto("fps").y()),
                  (3.1, self.punto("pomodoro").x(), self.punto("pomodoro").y()),
                  (5.2, self.punto("pomodoro").x(), self.punto("pomodoro").y())]
        pos = camino(t, puntos)
        cursor(p, pos, clic(p, pos, t, 1.55) + clic(p, pos, t, 3.15))


class Cierre(Escena):
    duracion = 4.0

    def pintar(self, p, t):
        fondo_oscuro(p, t + 3)
        k = tramo(t, 0.1, 0.7)
        tam = 96 * rebote(k, 1.3)
        if tam > 1:
            estilo.dibujar_logo(p, QRectF(W / 2 - tam / 2, 190 - tam / 2, tam, tam))
        p.save()
        p.setOpacity(salida(tramo(t, 0.3, 0.8)))
        texto(p, QRectF(0, 250, W, 60), "Orbit", 34, "#ffffff", QFont.DemiBold, Qt.AlignCenter, titulo=True)
        texto(p, QRectF(0, 310, W, 28), "Gratis y de código abierto", 14, QColor(255, 255, 255, 200),
              alineado=Qt.AlignCenter)
        p.restore()
        tipos = [plugin.icono for plugin in demo.plugins]
        total = len(tipos) * 44 + (len(tipos) - 1) * 14
        for i, tipo in enumerate(tipos):
            k = tramo(t, 0.6 + i * 0.07, 0.95 + i * 0.07)
            if k <= 0:
                continue
            tam = 44 * rebote(k, 1.5)
            cx = W / 2 - total / 2 + 22 + i * 58
            p.save()
            p.setOpacity(min(1.0, k * 2))
            estilo.dibujar_icono(p, QRectF(cx - tam / 2, 380 - tam / 2, tam, tam), tipo)
            p.restore()
        k = salida(tramo(t, 1.3, 1.8))
        if k > 0:
            p.save()
            p.setOpacity(k)
            p.setFont(fuente(12.5, QFont.DemiBold))
            enlace = "github.com/Abrahamdlt/Orbit"
            ancho = QFontMetricsF(p.font()).horizontalAdvance(enlace) + 44
            caja = QRectF(W / 2 - ancho / 2, 440, ancho, 42)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(estilo.paleta().acento))
            p.drawRoundedRect(caja, 21, 21)
            p.setPen(Qt.white)
            p.drawText(caja, Qt.AlignCenter, enlace)
            p.restore()


# ---------------------------------------------------------------- montaje

def crear_escenas():
    return [Intro(), EscenaPanel(), EscenaRueda(), EscenaFPS(), EscenaOCR(), EscenaPortapapeles(), EscenaColor(),
            EscenaMas(), EscenaAjustes(), Cierre()]


def linea_de_tiempo(escenas):
    inicios, t = [], 0.0
    for escena in escenas:
        inicios.append(t)
        t += escena.duracion - FUNDIDO
    return inicios, t + FUNDIDO


def fotograma(escenas, inicios, t):
    activas = [(e, t - i) for e, i in zip(escenas, inicios) if i <= t < i + e.duracion]
    img = lienzo()
    img.fill(Qt.black)
    p = pintor(img)
    for indice, (escena, local) in enumerate(activas):
        if indice == 0:
            escena.pintar(p, local)
            continue
        encima = lienzo()
        encima.fill(Qt.black)
        q = pintor(encima)
        escena.pintar(q, local)
        q.end()
        p.save()
        p.setOpacity(suave(tramo(local, 0, FUNDIDO)))
        p.drawImage(QPointF(0, 0), encima)
        p.restore()
    # al final, fundido a negro
    total = inicios[-1] + escenas[-1].duracion
    negro = tramo(t, total - 0.5, total)
    if negro > 0:
        p.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0, int(255 * negro)))
    p.end()
    return img


def main():
    escenas = crear_escenas()
    inicios, total = linea_de_tiempo(escenas)
    if "--fotos" in sys.argv:
        carpeta = os.path.join(SALIDA, "fotos")
        os.makedirs(carpeta, exist_ok=True)
        for valor in sys.argv[sys.argv.index("--fotos") + 1:]:
            t = float(valor)
            fotograma(escenas, inicios, t).save(os.path.join(carpeta, f"t{t:05.1f}.png"))
        print("Fotos guardadas en", carpeta, "| duración total %.1f s" % total)
        return
    import imageio_ffmpeg
    destino = os.path.join(SALIDA, "Orbit-demo.mp4")
    ffmpeg = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
         "-s", f"{int(W * ESCALA)}x{int(H * ESCALA)}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
         "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", destino], stdin=subprocess.PIPE)
    cuadros = int(total * FPS)
    empezo = time.time()
    for n in range(cuadros):
        img = fotograma(escenas, inicios, n / FPS).convertToFormat(QImage.Format_ARGB32)
        ffmpeg.stdin.write(bytes(img.constBits()))
        if n % 150 == 0:
            print(f"{n}/{cuadros} cuadros ({time.time() - empezo:.0f} s)", flush=True)
    ffmpeg.stdin.close()
    ffmpeg.wait()
    print("Listo:", destino, f"({total:.1f} s, {os.path.getsize(destino) / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
