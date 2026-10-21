"""Plugin Pomodoro: una pastilla con la cuenta atrás de enfoque y descanso. El atajo inicia o pausa."""
import time
import winsound

from PySide6.QtCore import QTimer

from ... import estilo
from ...estilo import Interruptor, Segmentado
from ...pastilla import NOMBRES_POSICIONES, POSICIONES
from ...ui import Fila, grupo
from ..base import Plugin
from .temporizador import CICLO, CORTO, ENFOQUE, LARGO, NOMBRES, Temporizador
from .vista import PastillaPomodoro

OPCIONES = {ENFOQUE: [15, 20, 25, 30, 45, 50], CORTO: [3, 5, 10], LARGO: [10, 15, 20, 30]}
CLAVES = {ENFOQUE: "enfoque", CORTO: "corto", LARGO: "largo"}  # en la config


class PluginPomodoro(Plugin):
    id = "pomodoro"
    nombre = "Pomodoro"
    descripcion = ("Trabaja en bloques de enfoque con descansos entre medias. Una pastilla discreta muestra el "
                   "tiempo que queda y te avisa al cambiar de fase.")
    icono = "pomodoro"
    texto_atajo = "Iniciar o pausar"
    activo_por_defecto = False  # la pastilla aparece la primera vez que pulsas el atajo, no nada más instalar

    def __init__(self, app):
        super().__init__(app)
        self.temporizador = Temporizador(*(self.cfg.get(CLAVES[f], d) for f, d in
                                           ((ENFOQUE, 25), (CORTO, 5), (LARGO, 15))))
        self.pastilla = None
        self.reloj = QTimer(self, interval=1000)
        self.reloj.timeout.connect(self._tic)

    def estado(self):
        if not self.activo:
            return "Desactivado"
        t = self.temporizador
        return f"{NOMBRES[t.fase]} · {t.reloj()}" if t.corriendo else f"En pausa · {t.texto()}"

    def iniciar(self):
        if self.pastilla is None:
            self.pastilla = PastillaPomodoro(self.temporizador)
        self.pastilla.posicion = self.cfg.get("posicion", "abajo-derecha")
        self.pastilla.aparecer()

    def detener(self):
        """Ocultar la pastilla pausa la cuenta: no corre a escondidas."""
        self.temporizador.pausar(time.time())
        self.reloj.stop()
        if self.pastilla:
            self.pastilla.desaparecer()

    def al_atajo(self):
        if not self.activo:
            self.app.fijar_activo(self, True)
            if not self.activo:
                return
        t = self.temporizador
        self._cambios(t.alternar(time.time()))
        if t.corriendo:
            self.reloj.start()
        else:
            self.reloj.stop()
        self._refrescar()
        self.app.aviso.mostrar(self.icono, NOMBRES[t.fase] if t.corriendo else "En pausa", t.reloj())

    def _tic(self):
        self._cambios(self.temporizador.avanzar(time.time()))
        self._refrescar()

    def _cambios(self, fases):
        if not fases:
            return
        fase, t = fases[-1], self.temporizador
        if fase == ENFOQUE:
            detalle = f"{t.minutos[ENFOQUE]} minutos · enfoque {t.enfoques % CICLO + 1} de {CICLO}"
        else:
            detalle = f"{t.minutos[fase]} minutos para descansar"
        self.app.aviso.mostrar(self.icono, NOMBRES[fase], detalle)
        if self.cfg.get("sonido", True):
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)

    def _refrescar(self):
        if self.pastilla and self.activo:
            self.pastilla.refrescar()

    # --- ajustes
    def grupos_ajustes(self):
        filas = []
        for fase, titulo, detalle in ((ENFOQUE, "Enfoque", "Minutos de trabajo."),
                                      (CORTO, "Descanso corto", "Minutos, después de cada enfoque."),
                                      (LARGO, "Descanso largo", f"Minutos, cada {CICLO} enfoques.")):
            opciones = OPCIONES[fase]
            segmentado = Segmentado([str(m) for m in opciones])
            segmentado.setFixedWidth(56 * len(opciones))  # solo números: no hace falta que ocupe toda la fila
            actual = self.temporizador.minutos[fase]
            segmentado.fijar(opciones.index(actual) if actual in opciones else 0)
            segmentado.cambiado.connect(lambda i, f=fase: self._minutos(f, OPCIONES[f][i]))
            filas.append(Fila(titulo, detalle, segmentado))
        posicion = Segmentado(NOMBRES_POSICIONES)
        posicion.fijar(POSICIONES.index(self.cfg.get("posicion", "abajo-derecha")))
        posicion.cambiado.connect(self._posicion)
        sonido = Interruptor()
        sonido.fijar(self.cfg.get("sonido", True))
        sonido.toggled.connect(lambda valor: self.guardar(sonido=valor))
        reiniciar = estilo.boton("Reiniciar")
        reiniciar.clicked.connect(self._reiniciar)
        return [grupo(*filas, titulo="Duraciones"),
                grupo(Fila("Posición", "", posicion),
                      Fila("Sonido al cambiar de fase", "Además del aviso en pantalla.", sonido), titulo="Pastilla"),
                grupo(Fila("Empezar de cero", "Vuelve al primer enfoque del ciclo, en pausa.", reiniciar))]

    def _minutos(self, fase, minutos):
        self.guardar(**{CLAVES[fase]: minutos})
        self.temporizador.fijar_minutos(fase, minutos)
        self._refrescar()

    def _posicion(self, indice):
        self.guardar(posicion=POSICIONES[indice])
        if self.pastilla:
            self.pastilla.posicion = POSICIONES[indice]
            self._refrescar()

    def _reiniciar(self):
        self.temporizador.reiniciar()
        self.reloj.stop()
        self._refrescar()
        self.app.cambio.emit()
