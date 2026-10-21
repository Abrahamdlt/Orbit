"""Lo que todo plugin de Orbit tiene en común."""
from PySide6.QtCore import QObject


class Plugin(QObject):
    id = ""
    nombre = ""
    descripcion = ""
    icono = "general"         # ver estilo.ICONOS
    requiere_admin = False
    motivo_admin = ""         # por qué necesita permisos (se muestra en el instalador y en ajustes)
    por_defecto = True        # marcado o no en el instalador
    activo_por_defecto = True  # si queda encendido al instalarlo con el instalador
    texto_atajo = "Activar o desactivar"  # qué hace el atajo (fila del atajo en Ajustes)
    modulos = ()              # módulos que carga al usarse: los comprueba Orbit.exe --probar-modulos

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

    def estado_atajo(self):
        """Estado de los plugins de acción: su atajo, que es lo que hay que recordar."""
        return self.cfg["atajo"]["texto"] if self.activo else "Desactivado"

    def al_atajo(self):
        """Lo que hace su atajo global. Por defecto, activarlo o desactivarlo."""
        self.app.fijar_activo(self, not self.activo)
        self.app.aviso.mostrar(self.icono, self.nombre, "Activado" if self.activo else "Desactivado")

    def avisar_desactivado(self):
        """Para los plugins de acción: su atajo no hace nada mientras están apagados."""
        self.app.aviso.mostrar(self.icono, self.nombre, "Está desactivado: actívalo desde Orbit")

    def guardar(self, **valores):
        self.cfg.update(valores)
        self.app.config.guardar()

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
