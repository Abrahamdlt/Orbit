"""Registro de plugins: el orden de esta lista es el del panel, los ajustes y el instalador.

Para añadir uno, crea su paquete con una clase que herede de base.Plugin y ponla aquí.
"""
from .despierto import PluginDespierto
from .encima import PluginEncima
from .fps import PluginFPS
from .radial import PluginRadial

CLASES = [PluginRadial, PluginFPS, PluginDespierto, PluginEncima]
