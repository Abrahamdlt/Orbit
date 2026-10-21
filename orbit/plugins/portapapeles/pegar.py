"""Volver a la ventana de antes y pegar con Ctrl+V (SendInput)."""
import ctypes
from ctypes import wintypes

from ...sistema import kernel32, user32

INPUT_KEYBOARD, KEYEVENTF_KEYUP = 1, 0x2
VK_CONTROL, VK_V = 0x11, 0x56
PROCESS_QUERY_LIMITED_INFORMATION, TOKEN_QUERY, TOKEN_ELEVATION = 0x1000, 0x8, 20


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _ENTRADA(ctypes.Union):
    # MOUSEINPUT es el miembro más grande: la unión debe medir lo mismo que en Windows
    _fields_ = [("ki", KEYBDINPUT), ("relleno", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("entrada", _ENTRADA)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.DWORD)]


def es_de_administrador(hwnd):
    """True si la ventana es de un programa abierto como administrador: Windows no deja pegarle (UIPI).
    Si ni siquiera se puede preguntar, se supone que sí."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    proceso = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not proceso:
        return True
    try:
        ficha = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(proceso, TOKEN_QUERY, ctypes.byref(ficha)):
            return True
        try:
            elevado, tam = wintypes.DWORD(), wintypes.DWORD()
            if not advapi32.GetTokenInformation(ficha, TOKEN_ELEVATION, ctypes.byref(elevado),
                                                ctypes.sizeof(elevado), ctypes.byref(tam)):
                return True
            return bool(elevado.value)
        finally:
            kernel32.CloseHandle(ficha)
    finally:
        kernel32.CloseHandle(proceso)


def activar(hwnd):
    if hwnd and user32.IsWindow(hwnd):
        user32.SetForegroundWindow(hwnd)


def ctrl_v():
    teclas = [(VK_CONTROL, 0), (VK_V, 0), (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)]
    entradas = (INPUT * len(teclas))()
    for entrada, (vk, banderas) in zip(entradas, teclas):
        entrada.type = INPUT_KEYBOARD
        entrada.entrada.ki = KEYBDINPUT(wVk=vk, dwFlags=banderas)
    return user32.SendInput(len(teclas), entradas, ctypes.sizeof(INPUT))
