"""Plugin Cambio de audio: el atajo pasa a la siguiente de tus salidas favoritas (audífonos, parlantes...)."""
import logging

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ... import estilo
from ...estilo import Interruptor
from ...ui import Fila, grupo
from ..base import Plugin


class PluginAudio(Plugin):
    id = "audio"
    nombre = "Cambio de audio"
    descripcion = ("Pasa de los audífonos a los parlantes (o a cualquier otra salida) con un atajo, sin abrir la "
                   "configuración de sonido. Tú eliges entre qué salidas va cambiando.")
    icono = "audio"
    texto_atajo = "Pasar a la siguiente salida"
    modulos = ("orbit.plugins.audio.dispositivos", "comtypes", "comtypes.client", "pycaw.utils",
               "pycaw.api.policyconfig", "pycaw.constants")

    def __init__(self, app):
        super().__init__(app)
        self._lista = None

    @property
    def favoritas(self):
        """[{"id", "nombre"}], en el orden en que se recorren. Se guarda el nombre para mostrarlas desconectadas."""
        return self.cfg.get("favoritas", [])

    def estado(self):
        if not self.activo:
            return "Desactivado"
        from . import dispositivos
        try:
            nombre = dispositivos.nombre_predeterminada()
        except Exception:
            logging.exception("No se pudo leer la salida de audio")
            nombre = None
        return f"Ahora: {nombre}" if nombre else self.cfg["atajo"]["texto"]

    def al_atajo(self):
        if not self.activo:
            self.avisar_desactivado()
            return
        from . import dispositivos
        try:
            conectadas = dict(dispositivos.salidas())
            actual = dispositivos.predeterminada()
        except Exception:
            logging.exception("No se pudieron leer las salidas de audio")
            self.app.aviso.mostrar(self.icono, "No se pudo leer el audio", "Windows no respondió")
            return
        disponibles = [f["id"] for f in self.favoritas if f["id"] in conectadas]
        if len(disponibles) < 2:
            if len(self.favoritas) < 2:
                self.app.aviso.mostrar(self.icono, "Elige tus salidas favoritas", "Marca dos o más en Ajustes")
                self.app.abrir_ajustes(self.id)
            else:
                self.app.aviso.mostrar(self.icono, "Solo hay una conectada",
                                       conectadas.get(disponibles[0], "") if disponibles else "Ninguna favorita")
            return
        siguiente = disponibles[(disponibles.index(actual) + 1) % len(disponibles)] if actual in disponibles \
            else disponibles[0]
        try:
            dispositivos.fijar(siguiente)
        except Exception:
            logging.exception("No se pudo cambiar la salida de audio")
            self.app.aviso.mostrar(self.icono, "No se pudo cambiar la salida", "Windows no lo permitió")
            return
        self.app.aviso.mostrar(self.icono, conectadas[siguiente], "Salida de audio")
        self._refrescar_lista()
        self.app.cambio.emit()

    # --- ajustes
    def grupos_ajustes(self):
        self._lista = QWidget()
        diseno = QVBoxLayout(self._lista)
        diseno.setContentsMargins(0, 0, 0, 0)
        self._refrescar_lista()
        actualizar = estilo.boton("Actualizar")
        actualizar.clicked.connect(self._refrescar_lista)
        return [self._lista,
                grupo(Fila("¿Conectaste algo nuevo?", "Vuelve a buscar las salidas de audio.", actualizar),
                      Fila("Qué cambia", "La salida predeterminada de Windows para todo: música, juegos, "
                                         "videollamadas y sonidos del sistema."),
                      titulo="Cómo funciona")]

    def _refrescar_lista(self):
        if self._lista is None:
            return
        try:
            diseno = self._lista.layout()
            while diseno.count():
                diseno.takeAt(0).widget().deleteLater()
        except RuntimeError:  # la página de ajustes se cerró
            self._lista = None
            return
        from . import dispositivos
        try:
            conectadas = dispositivos.salidas()
            actual = dispositivos.predeterminada()
        except Exception:
            logging.exception("No se pudieron leer las salidas de audio")
            diseno.addWidget(grupo(Fila("No se pudieron leer las salidas de audio", "Windows no respondió."),
                                   titulo="Salidas favoritas"))
            return
        ids = {f["id"] for f in self.favoritas}
        filas = []
        for id_dispositivo, nombre in conectadas:
            filas.append(self._fila(id_dispositivo, nombre, "Se oye por aquí ahora" if id_dispositivo == actual
                                    else "", id_dispositivo in ids))
        conectados = {i for i, _ in conectadas}
        for f in self.favoritas:
            if f["id"] not in conectados:
                filas.append(self._fila(f["id"], f["nombre"], "No está conectada", True))
        if not filas:
            filas = [Fila("No hay salidas de audio", "Conecta audífonos o parlantes y pulsa Actualizar.")]
        titulo = "Salidas favoritas"
        if len(conectadas) == 1 and len(self.favoritas) < 2:
            filas.append(Fila("Solo hay una salida conectada", "Conecta otra (audífonos, parlantes, un monitor "
                                                               "con altavoces...) para ir cambiando entre ellas."))
        diseno.addWidget(grupo(*filas, titulo=titulo))

    def _fila(self, id_dispositivo, nombre, detalle, marcada):
        interruptor = Interruptor()
        interruptor.fijar(marcada)
        interruptor.toggled.connect(lambda valor: self._marcar(id_dispositivo, nombre, valor))
        return Fila(nombre, detalle, interruptor)

    def _marcar(self, id_dispositivo, nombre, favorita):
        favoritas = [f for f in self.favoritas if f["id"] != id_dispositivo]
        if favorita:
            favoritas.append({"id": id_dispositivo, "nombre": nombre})
        self.guardar(favoritas=favoritas)
