"""Funciones de Windows (Win32) que usa Orbit."""
import ctypes
import os
import subprocess
import tempfile
import winreg
from ctypes import wintypes

from . import rutas

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
SIN_VENTANA = subprocess.CREATE_NO_WINDOW

WH_KEYBOARD_LL, VK_LBUTTON = 13, 0x01
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_HOTKEY = 0x100, 0x101, 0x104, 0x105, 0x312
MOD_NOREPEAT = 0x4000
LRESULT = ctypes.c_ssize_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wintypes.UINT]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.IsUserAnAdmin.restype = wintypes.BOOL


# ---------------------------------------------------------------- ventanas y procesos

def boton_izquierdo_presionado():
    return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


def pid_en_primer_plano():
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def nombre_de_proceso(pid):
    proceso = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not proceso:
        return ""
    try:
        buffer, tam = ctypes.create_unicode_buffer(260), wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(proceso, 0, buffer, ctypes.byref(tam)):
            return os.path.basename(buffer.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(proceso)


def programa_en_primer_plano():
    return nombre_de_proceso(pid_en_primer_plano())


def una_sola_instancia(nombre):
    """False si ya hay otra copia corriendo con ese nombre de mutex."""
    kernel32.CreateMutexW(None, False, nombre)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def siempre_encima(hwnd):
    """Vuelve a poner la ventana encima de todo (los juegos a veces la tapan)."""
    HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = -1, 0x2, 0x1, 0x10
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def tema_oscuro():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def barra_de_titulo_oscura(hwnd, oscura):
    valor = ctypes.c_int(1 if oscura else 0)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 20, ctypes.byref(valor), ctypes.sizeof(valor))


# ---------------------------------------------------------------- permisos de administrador

def es_admin():
    return bool(shell32.IsUserAnAdmin())


def ejecutar_como_admin(exe, argumentos="", esperar=True):
    """Muestra el aviso de Windows ("¿Permitir cambios?"). Devuelve el código de salida,
    0 si no se espera, o None si el usuario dijo que no."""
    info = SHELLEXECUTEINFOW(cbSize=ctypes.sizeof(SHELLEXECUTEINFOW), fMask=0x40,  # SEE_MASK_NOCLOSEPROCESS
                             lpVerb="runas", lpFile=exe, lpParameters=argumentos, nShow=0)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        return None
    if not esperar or not info.hProcess:
        return 0
    kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    codigo = wintypes.DWORD()
    kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(codigo))
    kernel32.CloseHandle(info.hProcess)
    return codigo.value


def pawnio_instalado():
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\PawnIO"))
        return True
    except OSError:
        return False


def tarea_existe(nombre=rutas.TAREA_AYUDANTE):
    return subprocess.run(["schtasks", "/query", "/tn", nombre], capture_output=True,
                          creationflags=SIN_VENTANA).returncode == 0


def ejecutar_tarea(nombre=rutas.TAREA_AYUDANTE):
    return subprocess.run(["schtasks", "/run", "/tn", nombre], capture_output=True,
                          creationflags=SIN_VENTANA).returncode == 0


def crear_tarea_admin(nombre, exe, argumentos, descripcion):
    """Tarea programada que corre como administrador sin volver a preguntar.
    Solo se puede crear siendo administrador (lo hace el ayudante al instalarse)."""
    usuario = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>{descripcion}</Description></RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>{usuario}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Priority>5</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>"{exe}"</Command><Arguments>{argumentos}</Arguments></Exec>
  </Actions>
</Task>"""
    archivo = os.path.join(tempfile.gettempdir(), "orbit_tarea.xml")
    with open(archivo, "w", encoding="utf-16") as f:
        f.write(xml)
    try:
        return subprocess.run(["schtasks", "/create", "/tn", nombre, "/xml", archivo, "/f"], capture_output=True,
                              creationflags=SIN_VENTANA).returncode == 0
    finally:
        os.remove(archivo)


def borrar_tarea(nombre=rutas.TAREA_AYUDANTE):
    subprocess.run(["schtasks", "/delete", "/tn", nombre, "/f"], capture_output=True, creationflags=SIN_VENTANA)


# ---------------------------------------------------------------- accesos directos

def crear_acceso(ruta, destino, argumentos=""):
    import win32com.client
    acceso = win32com.client.Dispatch("WScript.Shell").CreateShortcut(ruta)
    acceso.TargetPath = destino
    acceso.Arguments = argumentos
    acceso.WorkingDirectory = os.path.dirname(destino)
    acceso.Save()


def borrar_archivo(ruta):
    try:
        os.remove(ruta)
    except FileNotFoundError:
        pass
