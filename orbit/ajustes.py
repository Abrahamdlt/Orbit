"""Ventana de Ajustes al estilo de macOS: lista lateral de plugins y una página para cada uno."""
import webbrowser

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import REPOSITORIO, VERSION, estilo, rutas, sistema
from .dialogos import DialogoAtajo
from .estilo import IconoPlugin, Interruptor
from .ui import Fila, etiqueta, grupo

ALTO_ELEMENTO = 36


class Lateral(QWidget):
    """Lista de la izquierda con una pastilla de selección que se desliza."""
    elegido = Signal(int)

    def __init__(self, elementos):
        super().__init__()
        self.elementos = elementos  # [(tipo_icono, texto)]
        self.indice = 0
        self._y = 0.0
        self.setFixedWidth(220)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QVariantAnimation(self, duration=260, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._mover)
        self.arriba = 70

    def _mover(self, valor):
        self._y = valor
        self.update()

    def elegir(self, indice, animar=True):
        self.indice = indice
        if animar and not estilo.BAJO_CONSUMO:
            self._anim.stop()
            self._anim.setStartValue(self._y)
            self._anim.setEndValue(float(indice))
            self._anim.start()
        else:
            self._y = float(indice)
            self.update()

    def mousePressEvent(self, evento):
        indice = int((evento.position().y() - self.arriba) // ALTO_ELEMENTO)
        if 0 <= indice < len(self.elementos) and indice != self.indice:
            self.elegir(indice)
            self.elegido.emit(indice)

    def paintEvent(self, _):
        pal = estilo.paleta()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(pal.lateral))
        borde = QColor(pal.texto)
        borde.setAlpha(22)
        p.setPen(borde)
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        estilo.dibujar_logo(p, QRectF(20, 24, 28, 28))
        p.setPen(QColor(pal.texto))
        p.setFont(estilo.fuente(13, QFont.DemiBold, titulo=True))
        p.drawText(QRectF(58, 24, 140, 28), Qt.AlignVCenter, "Orbit")
        seleccion = QColor(pal.acento)
        p.setPen(Qt.NoPen)
        p.setBrush(seleccion)
        p.drawRoundedRect(QRectF(10, self.arriba + self._y * ALTO_ELEMENTO + 2, self.width() - 20, ALTO_ELEMENTO - 4),
                          8, 8)
        for i, (tipo, texto) in enumerate(self.elementos):
            y = self.arriba + i * ALTO_ELEMENTO
            estilo.dibujar_icono(p, QRectF(20, y + 8, 20, 20), tipo)
            cerca = max(0.0, 1 - abs(self._y - i))
            p.setPen(estilo.mezclar(pal.texto, "#FFFFFF", cerca))
            p.setFont(estilo.fuente(10, QFont.Medium))
            p.drawText(QRectF(50, y, self.width() - 60, ALTO_ELEMENTO), Qt.AlignVCenter, texto)


class Pagina(QScrollArea):
    def __init__(self, tipo, titulo, descripcion):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        contenido = QWidget()
        self.diseno = QVBoxLayout(contenido)
        self.diseno.setContentsMargins(34, 28, 34, 28)
        self.diseno.setSpacing(18)
        cabecera = QHBoxLayout()
        cabecera.setSpacing(16)
        cabecera.addWidget(IconoPlugin(tipo, 56), 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(4)
        textos.addWidget(etiqueta(titulo, "titulo"))
        textos.addWidget(etiqueta(descripcion, "secundario", envolver=True))
        cabecera.addLayout(textos, 1)
        self.diseno.addLayout(cabecera)
        self.setWidget(contenido)

    def agregar(self, *widgets):
        for w in widgets:
            self.diseno.addWidget(w)

    def terminar(self):
        self.diseno.addStretch()


class PaginaPlugin(Pagina):
    def __init__(self, app, plugin):
        super().__init__(plugin.icono, plugin.nombre, plugin.descripcion)
        self.app, self.plugin = app, plugin
        self.interruptor = Interruptor()
        self.interruptor.toggled.connect(lambda v: app.fijar_activo(plugin, v))
        self.anadir = estilo.boton("Añadir", "primario")
        self.anadir.clicked.connect(lambda: app.instalar_plugin(plugin))
        controles = QWidget()
        fila_controles = QHBoxLayout(controles)
        fila_controles.setContentsMargins(0, 0, 0, 0)
        fila_controles.addWidget(self.interruptor)
        fila_controles.addWidget(self.anadir)
        self.fila_estado = Fila("Activado", "", controles)
        filas = [self.fila_estado]
        if plugin.requiere_admin:
            filas.append(Fila("Necesita permiso de administrador", plugin.motivo_admin))
        self.agregar(grupo(*filas))

        self.boton_atajo = estilo.boton(plugin.cfg["atajo"]["texto"])
        self.boton_atajo.clicked.connect(self._cambiar_atajo)
        self.fila_atajo = Fila("Activar o desactivar", "", self.boton_atajo)
        self.agregar(grupo(self.fila_atajo, titulo="Atajo de teclado"))
        self.extras = QWidget()
        self.extras_diseno = QVBoxLayout(self.extras)
        self.extras_diseno.setContentsMargins(0, 0, 0, 0)
        self.extras_diseno.setSpacing(18)
        self.agregar(self.extras)
        self.terminar()
        self.refrescar()

    def refrescar(self):
        instalado = self.plugin.instalado
        self.interruptor.setVisible(instalado)
        self.anadir.setVisible(not instalado)
        self.interruptor.fijar(self.plugin.activo)
        self.fila_estado.titulo.setText("Activado" if instalado else "No está instalado")
        self.fila_estado.fijar_detalle("" if instalado else "Pulsa Añadir para instalarlo.")
        self.boton_atajo.setText(self.plugin.cfg["atajo"]["texto"])
        ok = self.app.atajo_ok.get(self.plugin.id, True)
        self.fila_atajo.fijar_detalle("" if ok else "Otro programa está usando este atajo: elige otro.")
        self.extras.setVisible(instalado)
        if instalado and not self.extras_diseno.count():
            for g in self.plugin.grupos_ajustes():
                self.extras_diseno.addWidget(g)

    def _cambiar_atajo(self):
        dialogo = DialogoAtajo(self.plugin.nombre, self.plugin.cfg["atajo"], self.app.atajos)
        if dialogo.exec() and dialogo.resultado:
            self.app.fijar_atajo(self.plugin, dialogo.resultado)


class PaginaGeneral(Pagina):
    def __init__(self, app):
        super().__init__("general", "General", "Ajustes de Orbit y sus plugins.")
        inicio = Interruptor()
        inicio.fijar(app.config["iniciar_con_windows"])
        inicio.toggled.connect(app.fijar_inicio_con_windows)
        self.agregar(grupo(Fila("Iniciar con Windows", "Orbit se abre sola al encender el equipo.", inicio)))
        bajo = Interruptor()
        bajo.fijar(app.config["bajo_consumo"])
        bajo.toggled.connect(app.fijar_bajo_consumo)
        self.agregar(grupo(
            Fila("Modo bajo consumo", "Sin animaciones ni efecto vidrio, el Medidor FPS se actualiza cada 2 segundos "
                                      "y Ajustes se libera de la memoria al cerrarla.", bajo),
            Fila("Ahorro extra en el Medidor FPS", "Apagar «Temperaturas» en el Medidor ahorra unos 100 MB: el "
                                                  "ayudante ya no carga los sensores."),
            titulo="Rendimiento"))
        github = estilo.boton("Ver en GitHub", "enlace")
        github.clicked.connect(lambda: webbrowser.open(REPOSITORIO))
        self.agregar(grupo(Fila("Versión", f"Orbit {VERSION}"),
                           Fila("Código abierto", "Puedes revisar todo el código y descargar nuevas versiones.",
                                github), titulo="Acerca de"))
        if rutas.esta_instalado_aqui():
            desinstalar = estilo.boton("Desinstalar…", "peligro")
            desinstalar.clicked.connect(app.desinstalar)
            self.agregar(grupo(Fila("Desinstalar Orbit", "Quita Orbit y sus plugins de este equipo.", desinstalar)))
        self.terminar()


class VentanaAjustes(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Ajustes de Orbit")
        self.setWindowIcon(estilo.icono_orbit())
        self.resize(860, 600)
        self.setMinimumSize(720, 480)
        self.paleta = estilo.paleta()
        self.setStyleSheet(estilo.hoja_de_estilo(self.paleta) + f"VentanaAjustes {{ background: {self.paleta.fondo}; }}")
        self.setAttribute(Qt.WA_StyledBackground)
        sistema.barra_de_titulo_oscura(int(self.winId()), self.paleta.oscuro)

        self.claves = [p.id for p in app.plugins] + ["general"]
        self.lateral = Lateral([(p.icono, p.nombre) for p in app.plugins] + [("general", "General")])
        self.paginas = QStackedWidget()
        self.paginas_plugin = {}
        for plugin in app.plugins:
            pagina = PaginaPlugin(app, plugin)
            self.paginas_plugin[plugin.id] = pagina
            self.paginas.addWidget(pagina)
        self.paginas.addWidget(PaginaGeneral(app))
        self.lateral.elegido.connect(self._mostrar)
        diseno = QHBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.setSpacing(0)
        diseno.addWidget(self.lateral)
        diseno.addWidget(self.paginas, 1)

    def _mostrar(self, indice):
        self.paginas.setCurrentIndex(indice)
        if estilo.BAJO_CONSUMO:
            return
        efecto = QGraphicsOpacityEffect(self.paginas.currentWidget())
        self.paginas.currentWidget().setGraphicsEffect(efecto)
        anim = QPropertyAnimation(efecto, b"opacity", self, duration=200, startValue=0.0, endValue=1.0,
                                  easingCurve=QEasingCurve.OutCubic)
        anim.finished.connect(lambda: self.paginas.currentWidget().setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def ir_a(self, clave):
        indice = self.claves.index(clave) if clave in self.claves else 0
        self.lateral.elegir(indice, animar=False)
        self.paginas.setCurrentIndex(indice)

    def refrescar(self):
        for pagina in self.paginas_plugin.values():
            pagina.refrescar()

    def closeEvent(self, evento):
        # En bajo consumo la ventana no se guarda: se libera y se vuelve a crear al abrirla
        if estilo.BAJO_CONSUMO:
            self.app.ventana_ajustes = None
            self.deleteLater()
        super().closeEvent(evento)
