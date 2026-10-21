"""Instalador de Orbit: corre al abrir el Orbit.exe descargado (fuera de la carpeta de instalación)."""
import logging
import os
import shutil
import subprocess
import sys
import threading

from PySide6.QtCore import QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from . import VERSION, ayudante, estilo, rutas, sistema
from .config import Config
from .estilo import Cargando, IconoPlugin, Interruptor
from .plugins import CLASES
from .ui import Fila, etiqueta, grupo


class Pagina(QWidget):
    def __init__(self):
        super().__init__()
        self.diseno = QVBoxLayout(self)
        self.diseno.setContentsMargins(40, 34, 40, 28)
        self.diseno.setSpacing(14)
        self.botonera = QHBoxLayout()

    def pie(self, *botones):
        self.diseno.addStretch()
        self.botonera.addStretch()
        for b in botones:
            self.botonera.addWidget(b)
        self.diseno.addLayout(self.botonera)


class Check(QWidget):
    """Marca verde dibujada que aparece al terminar."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(84, 84)

    def paintEvent(self, _):
        pal = estilo.paleta()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(pal.verde))
        p.drawEllipse(QRectF(4, 4, 76, 76))
        p.setPen(QPen(Qt.white, 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline([QPoint(26, 43), QPoint(37, 54), QPoint(58, 32)])


class _Hilo(QObject):
    paso = Signal(str)
    listo = Signal(list)


class Instalador(QWidget):
    def __init__(self):
        super().__init__()
        self.paleta = estilo.paleta()
        self.anterior = Config() if os.path.exists(rutas.CONFIG) else None
        self.actualizando = os.path.exists(rutas.EXE_INSTALADO)
        estilo.BAJO_CONSUMO = bool(self.anterior and self.anterior["bajo_consumo"])
        self.setWindowTitle("Instalar Orbit")
        self.setWindowIcon(estilo.icono_orbit())
        self.setFixedSize(620, 680)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(estilo.hoja_de_estilo(self.paleta) + f"Instalador {{ background: {self.paleta.fondo}; }}")
        sistema.barra_de_titulo_oscura(int(self.winId()), self.paleta.oscuro)
        self.paginas = QStackedWidget()
        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.paginas)
        self.hilo = _Hilo()
        self.hilo.paso.connect(lambda texto: self.estado.setText(texto))
        self.hilo.listo.connect(self._terminado)
        for pagina in (self._bienvenida(), self._antes(), self._plugins(), self._progreso()):
            self.paginas.addWidget(pagina)

    # --- páginas
    def _bienvenida(self):
        pagina = Pagina()
        logo = QLabel()
        logo.setPixmap(estilo.pixmap_logo(192))
        logo.setFixedSize(96, 96)
        logo.setScaledContents(True)
        titulo = etiqueta("Bienvenido a Orbit", "titulo")
        titulo.setFont(estilo.fuente(24, QFont.DemiBold, titulo=True))
        texto = ("Ya tienes Orbit instalado: esto lo actualiza a la versión " + VERSION + "." if self.actualizando else
                 "Pequeñas herramientas que viven junto al reloj de Windows.")
        subtitulo = etiqueta(texto, "secundario", envolver=True)
        subtitulo.setFixedWidth(460)
        for w in (logo, titulo, subtitulo):
            pagina.diseno.addWidget(w, 0, Qt.AlignHCenter)
        subtitulo.setAlignment(Qt.AlignCenter)
        pagina.diseno.insertStretch(0)
        continuar = estilo.boton("Continuar", "primario")
        continuar.clicked.connect(lambda: self._ir(1))
        pagina.pie(continuar)
        return pagina

    def _antes(self):
        pagina = Pagina()
        pagina.diseno.addWidget(etiqueta("Antes de empezar", "titulo"))
        pagina.diseno.addWidget(etiqueta("Unas cosas que conviene saber. Nada de esto es grave.", "secundario"))
        pagina.diseno.addWidget(grupo(
            Fila("Windows puede mostrar un aviso",
                 "Orbit es nueva y no tiene una firma digital de pago, así que Windows o el antivirus pueden mostrar "
                 "«Windows protegió tu PC». Pulsa «Más información» y luego «Ejecutar de todas formas»."),
            Fila("Por qué puedes confiar",
                 "Orbit no se conecta a internet y no envía datos a nadie: hasta el reconocimiento de texto ocurre "
                 "en tu equipo. Cada plugin actúa solo con su atajo, y todo el código es público en GitHub."),
            Fila("Historial del portapapeles",
                 "Guarda en memoria lo que copias (en disco solo si lo pides) y no guarda lo que copian los gestores "
                 "de contraseñas. Viene sin marcar: elígelo si lo quieres."),
            Fila("Juegos en pantalla completa exclusiva",
                 "El Medidor FPS no puede dibujarse encima en ese modo. Usa «ventana sin bordes» en el juego."),
            Fila("Conversiones de Office",
                 "Las opciones de Word, Excel y PowerPoint aparecen solo si el equipo tiene Microsoft Office.")))
        atras, continuar = estilo.boton("Atrás"), estilo.boton("Continuar", "primario")
        atras.clicked.connect(lambda: self._ir(0))
        continuar.clicked.connect(lambda: self._ir(2))
        pagina.pie(atras, continuar)
        return pagina

    def _plugins(self):
        pagina = Pagina()
        pagina.diseno.addWidget(etiqueta("Elige tus plugins", "titulo"))
        pagina.diseno.addWidget(etiqueta("Puedes añadir o quitar plugins más tarde desde Orbit.", "secundario"))
        self.elegidos = {}
        filas = []
        for clase in CLASES:
            interruptor = Interruptor()
            interruptor.fijar(self._marcado(clase))
            interruptor.toggled.connect(self._validar)
            self.elegidos[clase.id] = interruptor
            fila = QWidget()
            h = QHBoxLayout(fila)
            h.setContentsMargins(14, 12, 14, 12)
            h.setSpacing(12)
            h.addWidget(IconoPlugin(clase.icono, 36), 0, Qt.AlignTop)
            textos = QVBoxLayout()
            textos.setSpacing(2)
            nombre = QLabel(clase.nombre)
            nombre.setFont(estilo.fuente(10.5, QFont.DemiBold))
            textos.addWidget(nombre)
            textos.addWidget(etiqueta(clase.descripcion, "secundario", envolver=True))
            if clase.requiere_admin:
                aviso = etiqueta("Requiere permiso de administrador", envolver=True)
                aviso.setStyleSheet(f"color: {self.paleta.naranja}; font-weight: 600;")
                textos.addSpacing(4)
                textos.addWidget(aviso)
                textos.addWidget(etiqueta(clase.motivo_admin, "secundario", envolver=True))
            h.addLayout(textos, 1)
            h.addWidget(interruptor, 0, Qt.AlignTop)
            filas.append(fila)
        self.pawnio = Interruptor()
        self.pawnio.fijar(True)
        self.elegidos["fps"].toggled.connect(self.pawnio.setEnabled)
        fila_pawnio = Fila("Temperatura de CPU (Medidor FPS)",
                           "Instala el driver PawnIO, firmado y de código abierto. Sin él, la temperatura de la CPU "
                           "aparece vacía.", self.pawnio)
        if sistema.pawnio_instalado():
            fila_pawnio = Fila("Temperatura de CPU (Medidor FPS)", "El driver PawnIO ya está instalado.")
        filas.append(fila_pawnio)
        self.con_windows = Interruptor()
        self.con_windows.fijar(self.anterior["iniciar_con_windows"] if self.anterior else True)
        # La lista no cabe en la ventana: va en un área con desplazamiento, con los botones siempre a la vista
        contenido = QWidget()
        lista = QVBoxLayout(contenido)
        lista.setContentsMargins(0, 0, 10, 0)
        lista.setSpacing(14)
        lista.addWidget(grupo(*filas))
        lista.addWidget(grupo(Fila("Iniciar con Windows", "Orbit se abre sola al encender el equipo.",
                                   self.con_windows)))
        lista.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QScrollArea.NoFrame)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desplazable.setWidget(contenido)
        pagina.diseno.addWidget(desplazable, 1)
        atras = estilo.boton("Atrás")
        self.boton_instalar = estilo.boton("Actualizar" if self.actualizando else "Instalar", "primario")
        atras.clicked.connect(lambda: self._ir(1))
        self.boton_instalar.clicked.connect(self._instalar)
        pagina.pie(atras, self.boton_instalar)
        return pagina

    def _progreso(self):
        pagina = Pagina()
        pagina.diseno.addStretch()
        self.cargando = Cargando(34)
        self.check = Check()
        self.check.hide()
        self.titulo_final = etiqueta("Instalando…", "titulo")
        self.estado = etiqueta("", "secundario", envolver=True)
        self.estado.setAlignment(Qt.AlignCenter)
        self.estado.setFixedWidth(460)  # centrada y con ancho fijo: si no, Qt corta la última línea
        for w in (self.cargando, self.check, self.titulo_final, self.estado):
            pagina.diseno.addWidget(w, 0, Qt.AlignHCenter)
        self.resumen = QWidget()
        self.resumen_diseno = QVBoxLayout(self.resumen)
        self.resumen_diseno.setContentsMargins(0, 8, 0, 0)
        pagina.diseno.addWidget(self.resumen)
        self.abrir = estilo.boton("Abrir Orbit", "primario")
        self.abrir.hide()
        self.abrir.clicked.connect(self._abrir)
        pagina.pie(self.abrir)
        return pagina

    # --- navegación con deslizamiento
    def _ir(self, indice):
        actual = self.paginas.currentIndex()
        if indice == actual:
            return
        direccion = 1 if indice > actual else -1
        self.paginas.setCurrentIndex(indice)
        if estilo.BAJO_CONSUMO:
            return
        pagina = self.paginas.currentWidget()
        efecto = QGraphicsOpacityEffect(pagina)
        pagina.setGraphicsEffect(efecto)
        grupo_anim = QParallelAnimationGroup(self)
        grupo_anim.addAnimation(QPropertyAnimation(efecto, b"opacity", duration=260, startValue=0.0, endValue=1.0,
                                                   easingCurve=QEasingCurve.OutCubic))
        grupo_anim.addAnimation(QPropertyAnimation(pagina, b"pos", duration=320, startValue=QPoint(40 * direccion, 0),
                                                   endValue=QPoint(0, 0), easingCurve=estilo.resorte(0.6)))
        grupo_anim.finished.connect(lambda: pagina.setGraphicsEffect(None))
        grupo_anim.start(QParallelAnimationGroup.DeleteWhenStopped)

    def _marcado(self, clase):
        """Al actualizar se respeta lo que ya tenías; los plugins nuevos vienen marcados según su por_defecto."""
        if self.anterior and clase.id in self.anterior.plugins_guardados:
            return self.anterior.plugin(clase.id).get("instalado", False)
        return clase.por_defecto

    def _validar(self):
        self.boton_instalar.setEnabled(any(i.isChecked() for i in self.elegidos.values()))

    # --- instalación
    def _instalar(self):
        elegidos = {clave: i.isChecked() for clave, i in self.elegidos.items()}
        pawnio = self.pawnio.isChecked() if not sistema.pawnio_instalado() else False
        con_windows = self.con_windows.isChecked()
        self._ir(3)
        threading.Thread(target=self._trabajo, args=(elegidos, pawnio, con_windows), daemon=True).start()

    def _trabajo(self, elegidos, pawnio, con_windows):
        import pythoncom
        pythoncom.CoInitialize()
        resumen = []
        try:
            self.hilo.paso.emit("Cerrando la versión anterior…")
            _cerrar_orbit_instalada()
            tecla_antigua = _quitar_rueda_antigua()
            self.hilo.paso.emit("Copiando Orbit…")
            os.makedirs(rutas.INSTALACION, exist_ok=True)
            if rutas.CONGELADO:
                shutil.copy2(sys.executable, rutas.EXE_INSTALADO)
            sistema.crear_acceso(rutas.ACCESO_MENU, rutas.EXE_INSTALADO)
            if con_windows:
                sistema.crear_acceso(rutas.ACCESO_INICIO, rutas.EXE_INSTALADO)
            else:
                sistema.borrar_archivo(rutas.ACCESO_INICIO)

            config = Config()
            config["iniciar_con_windows"] = con_windows
            if tecla_antigua:
                config.plugin("radial").update(tecla_antigua)
            for clase in CLASES:
                cfg = config.plugin(clase.id)
                elegido, antes = elegidos[clase.id], cfg.get("instalado", False)
                if clase.requiere_admin and elegido:
                    self.hilo.paso.emit(f"{clase.nombre}: Windows te pedirá permiso…")
                    elegido = ayudante.registrado() and (not pawnio or sistema.pawnio_instalado()) \
                        or ayudante.instalar(pawnio)
                    resumen.append((clase.icono, clase.nombre, "Listo" if elegido else
                                    "Sin permiso: no se instaló. Puedes añadirlo después desde Orbit."))
                elif clase.requiere_admin and antes and not elegido:
                    ayudante.quitar()
                    resumen.append((clase.icono, clase.nombre, "Quitado"))
                elif elegido:
                    resumen.append((clase.icono, clase.nombre, "Listo"))
                cfg["instalado"] = elegido
                cfg["activo"] = elegido and (cfg.get("activo", True) or not antes)
            config.guardar()
            self.hilo.listo.emit(resumen)
        except Exception as error:
            logging.exception("Falló la instalación")
            self.hilo.listo.emit([("general", "No se pudo instalar", str(error))])

    def _terminado(self, resumen):
        self.cargando.hide()
        self.check.show()
        fallo = resumen and resumen[0][1] == "No se pudo instalar"
        self.titulo_final.setText("Algo salió mal" if fallo else "Orbit está lista")
        self.estado.setText("" if fallo else "La encontrarás junto al reloj, en la bandeja del sistema. "
                                             "Haz clic en su icono para ver tus plugins.")
        filas = []
        # Lo que salió bien va en una sola fila de iconos; lo demás (sin permiso, quitado, error), en filas aparte
        listos = [(icono, nombre) for icono, nombre, texto in resumen if texto == "Listo"]
        if listos:
            fila = QWidget()
            h = QHBoxLayout(fila)
            h.setContentsMargins(14, 10, 14, 10)
            h.setSpacing(6)
            for icono, nombre in listos:
                icono_plugin = IconoPlugin(icono, 24)
                icono_plugin.setToolTip(nombre)
                h.addWidget(icono_plugin)
            h.addStretch()
            h.addWidget(etiqueta(f"{len(listos)} plugin{'s' if len(listos) > 1 else ''} "
                                 f"listo{'s' if len(listos) > 1 else ''}", "secundario"))
            filas.append(fila)
        for icono, nombre, texto in resumen:
            if texto == "Listo":
                continue
            fila = QWidget()
            h = QHBoxLayout(fila)
            h.setContentsMargins(14, 8, 14, 8)
            h.addWidget(IconoPlugin(icono, 24))
            h.addWidget(QLabel(nombre))
            h.addStretch()
            h.addWidget(etiqueta(texto, "secundario", envolver=True), 2)
            filas.append(fila)
        if filas:
            self.resumen_diseno.addWidget(grupo(*filas))
        self.abrir.setVisible(not fallo)

    def _abrir(self):
        subprocess.Popen([rutas.EXE_INSTALADO, "--recien-instalada"], cwd=rutas.INSTALACION)
        self.close()


def _cerrar_orbit_instalada():
    import psutil
    propio = os.getpid()
    for proceso in psutil.process_iter(["exe", "pid"]):
        try:
            if proceso.info["pid"] != propio and proceso.info["exe"] and \
                    os.path.normcase(proceso.info["exe"]) == os.path.normcase(rutas.EXE_INSTALADO):
                proceso.kill()
        except (psutil.Error, OSError):
            pass


def _quitar_rueda_antigua():
    """Orbit reemplaza a la app «Rueda radial» suelta (la versión anterior). Devuelve la tecla que usaba."""
    import json
    import psutil
    carpeta = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "RuedaRadial")
    datos = os.path.join(os.environ["APPDATA"], "RuedaRadial")
    if not os.path.isdir(carpeta) and not os.path.isdir(datos):
        return None
    for proceso in psutil.process_iter(["exe"]):
        try:
            if proceso.info["exe"] and os.path.normcase(proceso.info["exe"]).startswith(os.path.normcase(carpeta)):
                proceso.kill()
        except (psutil.Error, OSError):
            pass
    tecla = None
    try:
        with open(os.path.join(datos, "config.json"), encoding="utf-8") as f:
            viejo = json.load(f)
        tecla = {"tecla_vk": viejo["tecla_vk"], "tecla_nombre": viejo["tecla_nombre"]}
    except (OSError, ValueError, KeyError):
        pass
    for acceso in (os.path.join(rutas.PROGRAMAS_MENU, "Startup", "Rueda Radial.lnk"),
                   os.path.join(rutas.PROGRAMAS_MENU, "Rueda Radial.lnk")):
        sistema.borrar_archivo(acceso)
    shutil.rmtree(carpeta, ignore_errors=True)
    shutil.rmtree(datos, ignore_errors=True)
    return tecla


def correr():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(estilo.fuente(10))
    ventana = Instalador()
    ventana.show()
    return app.exec()
