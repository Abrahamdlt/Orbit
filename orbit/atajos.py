"""Atajos de teclado globales (funcionan aunque Orbit no tenga el foco)."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from .config import MOD_ALT, MOD_CTRL, MOD_SHIFT
from .sistema import MOD_NOREPEAT, WM_HOTKEY, user32

ID_PRUEBA = 0xBFFF


def nombre_tecla(vk):
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    codigo = user32.MapVirtualKeyW(vk, 0)
    buffer = ctypes.create_unicode_buffer(32)
    if user32.GetKeyNameTextW(codigo << 16, buffer, 32):
        return buffer.value
    return f"Tecla {vk}"


def texto_atajo(mods, vk):
    partes = [n for m, n in ((MOD_CTRL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift")) if mods & m]
    return " + ".join(partes + [nombre_tecla(vk)])


class Atajos(QWidget):
    """Ventana invisible que recibe los WM_HOTKEY de Windows."""
    disparado = Signal(str)

    def __init__(self):
        super().__init__()
        self.hwnd = int(self.winId())
        self._numeros = {}  # clave del plugin -> id del atajo en Windows

    def registrar(self, clave, atajo):
        self.quitar(clave)
        numero = self._numeros.get(clave) or len(self._numeros) + 1
        if user32.RegisterHotKey(self.hwnd, numero, atajo["mods"] | MOD_NOREPEAT, atajo["vk"]):
            self._numeros[clave] = numero
            return True
        return False

    def quitar(self, clave):
        if clave in self._numeros:
            user32.UnregisterHotKey(self.hwnd, self._numeros[clave])

    def libre(self, mods, vk):
        """True si nadie más (Windows u otro programa) está usando esa combinación."""
        if user32.RegisterHotKey(self.hwnd, ID_PRUEBA, mods | MOD_NOREPEAT, vk):
            user32.UnregisterHotKey(self.hwnd, ID_PRUEBA)
            return True
        return False

    def nativeEvent(self, tipo, mensaje):
        msg = wintypes.MSG.from_address(int(mensaje))
        if msg.message == WM_HOTKEY:
            for clave, numero in self._numeros.items():
                if numero == msg.wParam:
                    self.disparado.emit(clave)
            return True, 0
        return False, 0
