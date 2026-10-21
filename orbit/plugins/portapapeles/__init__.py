"""Plugin Historial del portapapeles: recuerda lo último que copiaste y el atajo abre la lista para pegarlo otra vez."""
import hashlib
import json
import logging
import os
import shutil

from PySide6.QtCore import QBuffer, QByteArray, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QImage

from ... import estilo, rutas
from ...estilo import Interruptor, Segmentado
from ...sistema import user32
from ...ui import Fila, grupo
from ..base import Plugin
from . import pegar
from .historial import Historial, es_privado
from .lista import CARPETA_TEMPORAL, Lista, mime_de

ARCHIVO = os.path.join(rutas.DATOS, "portapapeles.json")
TAMANOS = [15, 30, 50, 100]
MAXIMO_TEXTO = 1_000_000  # caracteres: algo más grande no se guarda


def a_png(imagen):
    datos = QByteArray()
    buffer = QBuffer(datos)
    buffer.open(QBuffer.WriteOnly)
    imagen.save(buffer, "PNG")
    return bytes(datos.data())


class PluginPortapapeles(Plugin):
    id = "portapapeles"
    nombre = "Historial del portapapeles"
    descripcion = ("Recuerda lo último que copias (texto, imágenes y archivos) para pegarlo o arrastrarlo otra vez "
                   "cuando quieras, con buscador. No guarda lo que copian los gestores de contraseñas.")
    icono = "portapapeles"
    texto_atajo = "Abrir el historial"
    por_defecto = False  # guarda lo que copias: mejor que lo elija cada uno

    def __init__(self, app):
        super().__init__(app)
        self.historial = Historial(self._maximo())
        self.lista = None
        self._cargado = False
        self._escuchando = False
        # Muchos programas ponen lo copiado en varios pasos: se lee cuando terminan
        self._espera = QTimer(self, singleShot=True, interval=150)
        self._espera.timeout.connect(self._leer)
        self._guardado = QTimer(self, singleShot=True, interval=1000)
        self._guardado.timeout.connect(self._guardar_disco)
        self._fila_borrar = None

    def _maximo(self):
        maximo = self.cfg.get("maximo", 30)
        return maximo if maximo in TAMANOS else 30

    def estado(self):
        if not self.activo:
            return "Desactivado"
        n = len(self.historial.elementos)
        return f"{n} elemento{'s' if n != 1 else ''}" if n else self.cfg["atajo"]["texto"]

    def iniciar(self):
        if self.cfg.get("recordar") and not self._cargado:
            self._cargar_disco()
        if not self._escuchando:
            QGuiApplication.clipboard().dataChanged.connect(self._espera.start)
            self._escuchando = True

    def detener(self):
        if self._escuchando:
            QGuiApplication.clipboard().dataChanged.disconnect(self._espera.start)
            self._escuchando = False
        self._espera.stop()
        if self.cfg.get("recordar"):
            self._guardar_disco()
        if self.lista:
            self.lista.hide()
        shutil.rmtree(CARPETA_TEMPORAL, ignore_errors=True)  # las imágenes que se arrastraron

    # --- escuchar el portapapeles
    def _leer(self):
        try:
            mime = QGuiApplication.clipboard().mimeData()
            if mime is not None:
                self.procesar(mime)
        except Exception:
            logging.exception("No se pudo leer el portapapeles")

    def procesar(self, mime):
        """Guarda lo copiado, salvo que venga marcado como privado (contraseñas)."""
        if es_privado(mime.formats(), lambda formato: mime.data(formato).data()):
            logging.info("Portapapeles: contenido marcado como privado, no se guarda")
            return
        urls = mime.urls() if mime.hasUrls() else []
        if urls and all(url.isLocalFile() for url in urls):
            # Archivos o carpetas (Qt también los da como texto: por eso se miran antes)
            rutas = [os.path.normpath(url.toLocalFile()) for url in urls]
            clave = "f" + hashlib.sha1("\n".join(rutas).casefold().encode("utf-8", "surrogatepass")).hexdigest()
            elemento = Historial.archivos(rutas, clave)
        elif mime.hasText() and mime.text().strip():
            texto = mime.text()
            if len(texto) > MAXIMO_TEXTO:
                return
            clave = "t" + hashlib.sha1(texto.encode("utf-8", "surrogatepass")).hexdigest()
            elemento = Historial.texto(texto, clave)
        elif mime.hasImage():
            imagen = QImage(mime.imageData())
            if imagen.isNull():
                return
            imagen = imagen.convertToFormat(QImage.Format_ARGB32)
            clave = "i" + hashlib.sha1(imagen.constBits().tobytes()).hexdigest()
            anterior = self.historial.buscar_clave(clave)
            if anterior:  # la misma imagen otra vez: no hace falta volver a comprimirla
                elemento = Historial.imagen(anterior["png"], anterior["mini"], anterior["ancho"], anterior["alto"],
                                            clave)
            else:
                mini = imagen.scaled(104, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                elemento = Historial.imagen(a_png(imagen), a_png(mini), imagen.width(), imagen.height(), clave)
        else:
            return
        self.historial.agregar(elemento)
        self._cambio()

    def _cambio(self):
        if self.cfg.get("recordar"):
            self._guardado.start()
        if self.lista and self.lista.isVisible():
            self.lista.refrescar()
        self._refrescar_fila()
        self.app.cambio.emit()

    # --- la lista
    def al_atajo(self):
        if not self.activo:
            self.avisar_desactivado()
            return
        if self.lista is None:
            self.lista = Lista(self.historial)
            self.lista.elegido.connect(self._elegido)
            self.lista.fijado.connect(self._fijar)
            self.lista.quitado.connect(self._quitar)
            self.lista.no_existe.connect(self._no_existe)
        if self.lista.isVisible():
            self.lista.hide()
            return
        self.lista.abrir(QCursor.pos(), user32.GetForegroundWindow() or 0)

    def _elegido(self, elemento):
        mime = mime_de(elemento)
        if mime is None:
            self._no_existe()
            return
        QGuiApplication.clipboard().setMimeData(mime)  # archivos como archivos: en una carpeta se copian
        anterior = self.lista.anterior
        pegar.activar(anterior)
        if self.cfg.get("solo_copiar"):
            self.app.aviso.mostrar(self.icono, "Copiado", "Pégalo con Ctrl+V donde quieras")
        elif pegar.es_de_administrador(anterior):
            # Windows no deja que un programa normal escriba en uno de administrador (UIPI)
            self.app.aviso.mostrar(self.icono, "Copiado, pega con Ctrl+V", "Esa ventana es de administrador")
        else:
            QTimer.singleShot(80, pegar.ctrl_v)  # tiempo para que la ventana recupere el foco

    def _no_existe(self):
        self.app.aviso.mostrar(self.icono, "Ya no existe", "Se movió o se borró después de copiarlo")

    def _fijar(self, clave, fijado):
        self.historial.fijar(clave, fijado)
        self._cambio()

    def _quitar(self, clave):
        self.historial.quitar(clave)
        self._cambio()

    # --- en disco («Recordar al reiniciar»)
    def _cargar_disco(self):
        self._cargado = True
        try:
            with open(ARCHIVO, encoding="utf-8") as f:
                guardados = json.load(f)
            actuales = self.historial.elementos
            self.historial.desde_datos(guardados)
            for e in reversed(actuales):  # lo copiado en esta sesión va encima de lo recordado
                self.historial.agregar(e)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError):
            logging.exception("No se pudo leer el historial guardado")

    def _guardar_disco(self):
        if not self.cfg.get("recordar"):
            return
        try:
            os.makedirs(rutas.DATOS, exist_ok=True)
            with open(ARCHIVO, "w", encoding="utf-8") as f:
                json.dump(self.historial.a_datos(), f, ensure_ascii=False)
        except OSError:
            logging.exception("No se pudo guardar el historial")

    # --- ajustes
    def grupos_ajustes(self):
        tamano = Segmentado([str(t) for t in TAMANOS])
        tamano.setFixedWidth(64 * len(TAMANOS))
        tamano.fijar(TAMANOS.index(self._maximo()))
        tamano.cambiado.connect(self._tamano)
        recordar = Interruptor()
        recordar.fijar(self.cfg.get("recordar", False))
        recordar.toggled.connect(self._recordar)
        solo_copiar = Interruptor()
        solo_copiar.fijar(self.cfg.get("solo_copiar", False))
        solo_copiar.toggled.connect(lambda valor: self.guardar(solo_copiar=valor))
        borrar = estilo.boton("Borrar")
        borrar.clicked.connect(self._borrar)
        self._fila_borrar = Fila("Borrar historial", "", borrar)
        self._refrescar_fila()
        return [grupo(Fila("Tamaño del historial", "Elementos que guarda. Lo fijado no se borra nunca.", tamano),
                      Fila("Recordar al reiniciar", "Lo guarda en tu carpeta de usuario (%APPDATA%\\Orbit), sin "
                                                    "cifrar. Apagado, todo se olvida al cerrar Orbit.", recordar),
                      Fila("Solo copiar, sin pegar", "Al elegir un elemento solo se copia: lo pegas tú con Ctrl+V.",
                           solo_copiar),
                      self._fila_borrar, titulo="Historial"),
                grupo(Fila("Contraseñas", "No guarda lo que copian los gestores de contraseñas (Bitwarden, "
                                          "1Password, KeePass…) ni lo que Windows marca para no guardar."),
                      Fila("Archivos", "Si copias archivos o carpetas, se guardan como archivos: al pegarlos en una "
                                       "carpeta se copian ahí. Se recuerda dónde están, no su contenido."),
                      Fila("En la lista", "Escribe para buscar. ↑↓ para elegir, Enter pega, Ctrl+P fija un elemento "
                                          "y Supr lo quita. Con el ratón: clic para pegar, clic en la chincheta para "
                                          "fijar, o arrastra el elemento a otra ventana o a una carpeta."),
                      titulo="Cómo funciona")]

    def _refrescar_fila(self):
        if self._fila_borrar is None:
            return
        try:
            n = len(self.historial.elementos)
            self._fila_borrar.fijar_detalle(f"Ahora hay {n} elemento{'s' if n != 1 else ''}. Quita todo menos lo "
                                            "fijado." if n else "El historial está vacío.")
        except RuntimeError:  # la página de ajustes se cerró
            self._fila_borrar = None

    def _tamano(self, indice):
        self.guardar(maximo=TAMANOS[indice])
        self.historial.fijar_maximo(TAMANOS[indice])
        self._cambio()

    def _recordar(self, valor):
        self.guardar(recordar=valor)
        if valor:
            self._cargado = True  # lo que hay en memoria es lo más nuevo
            self._guardar_disco()
        else:
            try:
                os.remove(ARCHIVO)
            except FileNotFoundError:
                pass
            except OSError:
                logging.exception("No se pudo borrar el historial guardado")

    def _borrar(self):
        self.historial.limpiar()
        if self.lista:
            self.lista.miniaturas.clear()
        self._cambio()
