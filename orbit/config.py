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
    "plugins": {
        "radial": {"instalado": True, "activo": True, "atajo": atajo("R"),
                   "tecla_vk": 0x09, "tecla_nombre": "Tab", "notificaciones": False},
        "fps": {"instalado": False, "activo": False, "atajo": atajo("F"), "posicion": "arriba-izquierda",
                "metricas": {"fps": True, "cpu": True, "gpu": True, "ram": True}},
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
        try:
            with open(rutas.CONFIG, encoding="utf-8") as f:
                _mezclar(self.datos, json.load(f))
        except (OSError, ValueError):
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
