"""La lógica del Pomodoro, sin Qt: enfoque, descanso corto y, cada cuatro enfoques, un descanso largo.

Quien lo usa le pasa la hora (time.time()); así se puede probar sin esperar y no se pierde la cuenta si el
equipo se suspende.
"""
import math

ENFOQUE, CORTO, LARGO = "enfoque", "corto", "largo"
NOMBRES = {ENFOQUE: "Enfoque", CORTO: "Descanso", LARGO: "Descanso largo"}
CICLO = 4  # enfoques antes del descanso largo


class Temporizador:
    def __init__(self, enfoque=25, corto=5, largo=15):
        self.minutos = {ENFOQUE: enfoque, CORTO: corto, LARGO: largo}
        self.reiniciar()

    def reiniciar(self):
        self.fase = ENFOQUE
        self.enfoques = 0          # enfoques terminados desde el último reinicio
        self.restante = self.duracion(ENFOQUE)
        self.corriendo = False
        self._ultimo = None

    def duracion(self, fase):
        return self.minutos[fase] * 60

    def fijar_minutos(self, fase, minutos):
        """Si esa fase está a punto de empezar (sin tocar), se ajusta ya; si no, vale desde la próxima vez."""
        sin_empezar = self.fase == fase and not self.corriendo and self.restante == self.duracion(fase)
        self.minutos[fase] = minutos
        if sin_empezar:
            self.restante = self.duracion(fase)

    def iniciar(self, ahora):
        if not self.corriendo:
            self.corriendo, self._ultimo = True, ahora

    def pausar(self, ahora):
        cambios = self.avanzar(ahora)
        self.corriendo = False
        return cambios

    def alternar(self, ahora):
        if self.corriendo:
            return self.pausar(ahora)
        self.iniciar(ahora)
        return []

    def avanzar(self, ahora):
        """Descuenta el tiempo pasado. Devuelve las fases en las que entró (casi siempre ninguna)."""
        if not self.corriendo:
            return []
        pasado = max(0.0, ahora - self._ultimo)
        self._ultimo = ahora
        cambios = []
        while pasado >= self.restante:
            pasado -= self.restante
            self._siguiente()
            cambios.append(self.fase)
        self.restante -= pasado
        return cambios

    def _siguiente(self):
        if self.fase == ENFOQUE:
            self.enfoques += 1
            self.fase = LARGO if self.enfoques % CICLO == 0 else CORTO
        else:
            self.fase = ENFOQUE
        self.restante = self.duracion(self.fase)

    def en_ciclo(self):
        """Enfoques terminados en el ciclo actual de cuatro (para los puntitos de la pastilla)."""
        if self.fase == LARGO:
            return CICLO
        return self.enfoques % CICLO

    def reloj(self):
        minutos, segundos = divmod(math.ceil(self.restante), 60)
        return f"{minutos:02d}:{segundos:02d}"

    def texto(self):
        return f"{NOMBRES[self.fase]} {self.reloj()}"
