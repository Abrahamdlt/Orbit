"""Ventanas de Windows: cuál está delante, fijarla encima de las demás y el borde de color que la rodea."""
import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ... import estilo, sistema
from ...sistema import user32

HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
GWL_EXSTYLE, WS_EX_TOPMOST = -20, 0x8
DWMWA_EXTENDED_FRAME_BOUNDS = 9
ERROR_ACCESS_DENIED = 5
# El escritorio y la barra de tareas no se fijan
CLASES_IGNORADAS = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
WINDOWS_11 = sys.getwindowsversion().build >= 22000

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.restype = wintypes.UINT


def ventana_delante():
    return user32.GetForegroundWindow() or 0


def existe(hwnd):
    return bool(user32.IsWindow(hwnd))


def titulo(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buffer, 256)
    return buffer.value


def clase(hwnd):
    buffer = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buffer, 128)
    return buffer.value


def pid(hwnd):
    numero = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(numero))
    return numero.value


def programa(hwnd):
    return sistema.nombre_de_proceso(pid(hwnd))


def se_puede_fijar(hwnd):
    return bool(hwnd) and clase(hwnd) not in CLASES_IGNORADAS and pid(hwnd) != os.getpid()


def esta_encima(hwnd):
    return bool(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)


def fijar(hwnd, encima):
    """Devuelve None si salió bien, o el código de error de Windows."""
    ok = user32.SetWindowPos(hwnd, HWND_TOPMOST if encima else HWND_NOTOPMOST, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    error = ctypes.get_last_error()
    if not ok:
        return error or 1
    return None if esta_encima(hwnd) == encima else ERROR_ACCESS_DENIED


def rectangulo(hwnd):
    """Rectángulo visible en píxeles reales (sin el borde invisible para redimensionar de Windows 10 y 11)."""
    rect = wintypes.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
                                                  ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def visible(hwnd):
    return bool(user32.IsWindowVisible(hwnd)) and not user32.IsIconic(hwnd)


def escala(hwnd):
    return (user32.GetDpiForWindow(hwnd) or 96) / 96


class Borde(QWidget):
    """Marco fino del color de acento alrededor de una ventana fijada. No recibe clics."""
    MARGEN = 4  # puntos fuera de la ventana

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.hwnd = int(self.winId())
        self.exterior = True
        self.ultimo = None

    def seguir(self, ventana):
        """Coloca el marco alrededor de la ventana. Se mueve con SetWindowPos, en píxeles reales."""
        if not visible(ventana):
            self.ultimo = None
            self.hide()
            return
        x, y, ancho, alto = rectangulo(ventana)
        maximizada = bool(user32.IsZoomed(ventana))
        margen = 0 if maximizada else round(self.MARGEN * escala(ventana))
        nuevo = (x - margen, y - margen, ancho + 2 * margen, alto + 2 * margen)
        if nuevo == self.ultimo and self.isVisible():
            return
        self.ultimo, self.exterior = nuevo, not maximizada
        if not self.isVisible():
            self.show()
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, *nuevo, SWP_NOACTIVATE)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(estilo.paleta().acento)
        if self.exterior:  # anillo en el margen, por fuera de la ventana
            radio = (8 if WINDOWS_11 else 0) + self.MARGEN
            p.setPen(QPen(color, 2.5))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), radio, radio)
        else:  # maximizada: el borde va por dentro, en el filo de la pantalla
            p.setPen(QPen(color, 3))
            p.drawRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))
