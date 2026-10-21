"""Plugin Texto de pantalla: eliges un área con el ratón y su texto se copia al portapapeles (OCR de Windows)."""
import logging
import threading

from PySide6.QtCore import QBuffer, QByteArray, QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

from ...dialogos import informar
from ...estilo import Interruptor, Segmentado
from ...pantalla import SelectorPantalla
from ...ui import Fila, grupo
from ..base import Plugin

COMO_INSTALAR = ("Configuración → Hora e idioma → Idioma y región → junto al idioma, «…» → Opciones de idioma → "
                 "Reconocimiento óptico de caracteres → Descargar.")
MAXIMO_IDIOMAS = 4  # los que caben en el control de Ajustes, además de «Automático»


class _Puente(QObject):
    """Lleva el resultado del hilo del OCR a la interfaz."""
    listo = Signal(object, object)  # texto, error


def a_png(imagen):
    datos = QByteArray()
    buffer = QBuffer(datos)
    buffer.open(QBuffer.WriteOnly)
    imagen.save(buffer, "PNG")
    return bytes(datos.data())


def nombre_corto(nombre):
    """«Español (México)» → «Español»."""
    return nombre.split(" (")[0]


class PluginOCR(Plugin):
    id = "ocr"
    nombre = "Texto de pantalla"
    descripcion = ("Elige un área de la pantalla y su texto se copia al portapapeles, aunque sea una imagen, un "
                   "PDF escaneado o un video. Usa el reconocimiento de texto de Windows, sin internet.")
    icono = "ocr"
    texto_atajo = "Elegir un área y copiar su texto"
    modulos = ("orbit.plugins.ocr.motor", "winrt.windows.media.ocr", "winrt.windows.graphics.imaging",
               "winrt.windows.storage.streams", "winrt.windows.globalization", "winrt.windows.foundation",
               "winrt.windows.foundation.collections")

    def __init__(self, app):
        super().__init__(app)
        self.selector = None
        self.trabajando = False
        self.puente = _Puente()
        self.puente.listo.connect(self._listo)

    def estado(self):
        return self.estado_atajo()

    def al_atajo(self):
        if not self.activo:
            self.avisar_desactivado()
            return
        if self.trabajando:
            return
        if self.selector is None:
            self.selector = SelectorPantalla("area")
            self.selector.ayuda = "Arrastra sobre el texto que quieres copiar  ·  Esc para cancelar"
            self.selector.area.connect(self._leer)
        self.selector.abrir()

    def detener(self):
        if self.selector:
            self.selector.cerrar()

    def _leer(self, imagen):
        from . import motor
        lado = max(imagen.width(), imagen.height())
        # El texto de pantalla es pequeño: al doble de tamaño Windows lo lee mucho mejor
        if lado * 2 <= min(4000, motor.maximo()):
            imagen = imagen.scaled(imagen.width() * 2, imagen.height() * 2, Qt.IgnoreAspectRatio,
                                   Qt.SmoothTransformation)
        elif lado > motor.maximo():
            imagen = imagen.scaled(motor.maximo(), motor.maximo(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        png, idioma, saltos = a_png(imagen), self.cfg.get("idioma", ""), self.cfg.get("saltos", True)
        self.trabajando = True

        def trabajo():
            try:
                self.puente.listo.emit(motor.reconocer(png, idioma, saltos), None)
            except Exception as error:
                if not isinstance(error, motor.SinIdioma):
                    logging.exception("Falló el OCR")
                self.puente.listo.emit(None, error)

        threading.Thread(target=trabajo, daemon=True).start()

    def _listo(self, texto, error):
        from .motor import SinIdioma
        self.trabajando = False
        if isinstance(error, SinIdioma):
            elegido = self.cfg.get("idioma", "")
            informar("Falta un idioma para leer texto",
                     (f"El idioma elegido en Ajustes ({elegido}) ya no está instalado. " if elegido else
                      "Windows no tiene instalado ningún idioma de reconocimiento de texto. ")
                     + "Para añadirlo: " + COMO_INSTALAR)
            return
        if error is not None:
            self.app.aviso.mostrar(self.icono, "No se pudo leer el texto", str(error)[:60])
            return
        texto = texto.strip()
        if not texto:
            self.app.aviso.mostrar(self.icono, "No encontré texto", "Prueba con un área más grande o más clara")
            return
        QGuiApplication.clipboard().setText(texto)
        palabras = len(texto.split())
        self.app.aviso.mostrar(self.icono, "Texto copiado", f"{palabras} palabra{'s' if palabras != 1 else ''}")

    # --- ajustes
    def grupos_ajustes(self):
        from . import motor
        try:
            instalados = motor.idiomas()
        except Exception:
            logging.exception("No se pudieron leer los idiomas del OCR")
            instalados = None
        filas = []
        if instalados:
            mostrados = instalados[:MAXIMO_IDIOMAS]
            cortos = [nombre_corto(n) for _, n in mostrados]
            if len(set(cortos)) < len(cortos):  # dos variantes del mismo idioma: mejor la etiqueta
                cortos = [etiqueta for etiqueta, _ in mostrados]
            etiquetas = [""] + [etiqueta for etiqueta, _ in mostrados]
            idioma = Segmentado(["Automático"] + cortos)
            idioma.setMinimumWidth(90 * len(etiquetas))
            actual = self.cfg.get("idioma", "")
            idioma.fijar(etiquetas.index(actual) if actual in etiquetas else 0)
            idioma.cambiado.connect(lambda i: self.guardar(idioma=etiquetas[i]))
            filas.append(Fila("Idioma", "«Automático» usa los idiomas de tu Windows. Instalados: "
                                        + ", ".join(n for _, n in instalados) + ".", idioma))
        elif instalados is None:
            filas.append(Fila("Idioma", "No se pudo cargar el reconocimiento de texto de Windows."))
        else:
            filas.append(Fila("Idioma", "Windows no tiene ningún idioma de reconocimiento de texto instalado. "
                                        + COMO_INSTALAR))
        saltos = Interruptor()
        saltos.fijar(self.cfg.get("saltos", True))
        saltos.toggled.connect(lambda valor: self.guardar(saltos=valor))
        filas.append(Fila("Mantener saltos de línea", "Si está apagado, todo el texto queda en un solo párrafo.",
                          saltos))
        return [grupo(*filas, titulo="Lectura"),
                grupo(Fila("Sin internet", "Usa el reconocimiento de texto que trae Windows: la imagen no sale "
                                           "de tu equipo."),
                      Fila("Otros idiomas", "Para leer otro idioma, instálalo en " + COMO_INSTALAR),
                      titulo="Cómo funciona")]
