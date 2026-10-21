"""Ajustes guardados en %APPDATA%\\Orbit\\config.json."""
import copy
import json
import os

from . import rutas

MOD_ALT, MOD_CTRL, MOD_SHIFT = 0x1, 0x2, 0x4


def atajo(letra):
    return {"mods": MOD_CTRL | MOD_ALT | MOD_SHIFT, "vk": ord(letra), "texto": f"Ctrl + Alt + Shift + {letra}"}


DEFECTO = {
    "iniciar_con_windows": True,
    "bajo_consumo": False,
    "plugins": {
        "radial": {"instalado": True, "activo": True, "atajo": atajo("R"),
                   "tecla_vk": 0x09, "tecla_nombre": "Tab", "notificaciones": False},
        "fps": {"instalado": False, "activo": False, "atajo": atajo("F"), "posicion": "arriba-izquierda",
                "baja_latencia": False, "temperaturas": True,
                "metricas": {"fps": True, "cpu": True, "gpu": True, "ram": True}},
        "despierto": {"instalado": False, "activo": False, "atajo": atajo("D"), "duracion": 60, "pantalla": True},
        "encima": {"instalado": False, "activo": True, "atajo": atajo("P"), "borde": True},
        "pomodoro": {"instalado": False, "activo": True, "atajo": atajo("O"), "enfoque": 25, "corto": 5, "largo": 15,
                     "posicion": "abajo-derecha", "sonido": True},
        "color": {"instalado": False, "activo": True, "atajo": atajo("C"), "formato": "hex", "historial": []},
        "ocr": {"instalado": False, "activo": True, "atajo": atajo("T"), "idioma": "", "saltos": True},
    },
}


def _mezclar(base, guardado):
    for clave, valor in guardado.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _mezclar(base[clave], valor)
        else:
            base[clave] = valor
    return base


class Config:
    def __init__(self):
        self.datos = copy.deepcopy(DEFECTO)
        self.plugins_guardados = set()  # plugins que ya estaban en el archivo (el resto es nuevo en esta versión)
        try:
            with open(rutas.CONFIG, encoding="utf-8") as f:
                guardado = json.load(f)
            self.plugins_guardados = set(guardado.get("plugins", {}))
            _mezclar(self.datos, guardado)
        except (OSError, ValueError, AttributeError):
            pass

    def __getitem__(self, clave):
        return self.datos[clave]

    def __setitem__(self, clave, valor):
        self.datos[clave] = valor

    def plugin(self, id_plugin):
        return self.datos["plugins"].setdefault(id_plugin, {})

    def guardar(self):
        os.makedirs(rutas.DATOS, exist_ok=True)
        with open(rutas.CONFIG, "w", encoding="utf-8") as f:
            json.dump(self.datos, f, indent=2, ensure_ascii=False)
