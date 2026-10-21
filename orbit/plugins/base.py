"""Lo que todo plugin de Orbit tiene en común."""
from PySide6.QtCore import QObject


class Plugin(QObject):
    id = ""
    nombre = ""
    descripcion = ""
    icono = "general"         # ver estilo.ICONOS
    requiere_admin = False
    motivo_admin = ""         # por qué necesita permisos (se muestra en el instalador y en ajustes)

    def __init__(self, app):
        super().__init__()
        self.app = app

    @property
    def cfg(self):
        return self.app.config.plugin(self.id)

    @property
    def instalado(self):
        return self.cfg.get("instalado", False)

    @property
    def activo(self):
        return self.instalado and self.cfg.get("activo", False)

    def estado(self):
        """Texto corto para el panel de la bandeja."""
        return "Activado" if self.activo else "Desactivado"

    def iniciar(self):
        """Se llama al activarse."""

    def detener(self):
        """Se llama al desactivarse o al cerrar Orbit."""

    def instalar(self, opciones=None):
        """Prepara lo que el plugin necesite (por ejemplo, permisos). Devuelve True si quedó listo."""
        return True

    def grupos_ajustes(self):
        """Grupos extra para su página en Ajustes (ver orbit.ui.grupo)."""
        return []
