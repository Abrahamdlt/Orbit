"""Plugin Medidor FPS: FPS, CPU, GPU y RAM en una pastilla flotante sobre cualquier ventana."""
from ... import ayudante, estilo, sistema
from ...estilo import Interruptor, Segmentado
from ...ui import Fila, grupo
from ..base import Plugin
from .overlay import Medidor
from .sensores import Lector

POSICIONES = ["arriba-izquierda", "arriba-derecha", "abajo-izquierda", "abajo-derecha"]


class PluginFPS(Plugin):
    id = "fps"
    nombre = "Medidor FPS"
    descripcion = ("Muestra FPS, uso y temperatura de CPU y GPU, y uso de RAM en una pastilla discreta encima de "
                   "cualquier ventana o juego.")
    icono = "fps"
    requiere_admin = True
    motivo_admin = ("Para contar los FPS de otros programas y leer la temperatura de la CPU, Windows exige permiso "
                    "de administrador. Se pide una sola vez; el ayudante solo lee datos y no cambia nada.")

    def __init__(self, app):
        super().__init__(app)
        self.medidor = None
        self.lector = Lector()
        self.lector.datos.connect(self._datos)
        self._fila_estado = None

    def estado(self):
        return f"Activado · {self.cfg['atajo']['texto']}" if self.activo else "Desactivado"

    def iniciar(self):
        if self.medidor is None:
            self.medidor = Medidor()
        self.medidor.metricas = self.cfg["metricas"]
        self.medidor.posicion = self.cfg["posicion"]
        self.lector.arrancar()
        self.medidor.aparecer()

    def detener(self):
        self.lector.parar()
        if self.medidor:
            self.medidor.desaparecer()

    def instalar(self, opciones=None):
        pawnio = (opciones or {}).get("pawnio", True)
        if ayudante.registrado() and (sistema.pawnio_instalado() or not pawnio):
            return True
        return ayudante.instalar(pawnio)

    def _datos(self, lectura):
        if self.medidor:
            self.medidor.actualizar(lectura)
        if self._fila_estado is not None:
            try:
                self._fila_estado.fijar_detalle(self._texto_estado(lectura))
            except RuntimeError:  # la página de ajustes se cerró
                self._fila_estado = None

    def _texto_estado(self, lectura=None):
        if not self.activo:
            return "Se comprueba al activar el medidor."
        conectado = (lectura or {}).get("ayudante", self.lector.ayudante_conectado)
        if conectado:
            return "Funcionando: FPS y temperatura de CPU disponibles."
        return "Sin el ayudante: solo uso de CPU, RAM y GPU NVIDIA. Pulsa Reparar para volver a darle permiso."

    # --- ajustes
    def grupos_ajustes(self):
        filas_metricas = []
        for clave, titulo, detalle in (("fps", "FPS", "Del programa o juego que tienes delante."),
                                       ("cpu", "CPU", "Uso y temperatura."),
                                       ("gpu", "GPU", "Uso y temperatura."),
                                       ("ram", "RAM", "Uso de memoria.")):
            interruptor = Interruptor()
            interruptor.fijar(self.cfg["metricas"].get(clave, True))
            interruptor.toggled.connect(lambda valor, c=clave: self._metrica(c, valor))
            filas_metricas.append(Fila(titulo, detalle, interruptor))

        posicion = Segmentado(["Arriba izq.", "Arriba der.", "Abajo izq.", "Abajo der."])
        posicion.fijar(POSICIONES.index(self.cfg["posicion"]))
        posicion.cambiado.connect(self._posicion)

        reparar = estilo.boton("Reparar")
        reparar.clicked.connect(lambda: self.instalar({"pawnio": False}) and self.app.reiniciar_plugin(self))
        self._fila_estado = Fila("Lectura avanzada", self._texto_estado(), reparar)
        if sistema.pawnio_instalado():
            fila_pawnio = Fila("Temperatura de CPU", "Driver PawnIO instalado.")
        else:
            instalar = estilo.boton("Instalar driver")
            instalar.clicked.connect(lambda: ayudante.instalar(True) and self.app.reiniciar_plugin(self))
            fila_pawnio = Fila("Temperatura de CPU", "Necesita el driver PawnIO (firmado y de código abierto). "
                                                     "Sin él, la temperatura de CPU aparece vacía.", instalar)
        nota = Fila("Juegos en pantalla completa exclusiva",
                    "En ese modo Windows no deja dibujar nada encima. Usa «ventana sin bordes» en el juego.")
        return [grupo(*filas_metricas, titulo="Qué mostrar"),
                grupo(Fila("Posición", "", posicion), titulo="Dónde"),
                grupo(self._fila_estado, fila_pawnio, nota, titulo="Lectura")]

    def _metrica(self, clave, valor):
        self.cfg["metricas"][clave] = valor
        self.app.config.guardar()
        if self.medidor:
            self.medidor.metricas = self.cfg["metricas"]
            self.medidor.actualizar(self.medidor.lectura)

    def _posicion(self, indice):
        self.cfg["posicion"] = POSICIONES[indice]
        self.app.config.guardar()
        if self.medidor:
            self.medidor.posicion = self.cfg["posicion"]
            self.medidor.actualizar(self.medidor.lectura)
