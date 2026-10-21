"""Piezas para armar páginas de ajustes al estilo de macOS: grupos redondeados con filas."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def etiqueta(texto, nombre=None, envolver=False):
    e = QLabel(texto)
    if nombre:
        e.setObjectName(nombre)
    if envolver:
        e.setWordWrap(True)
    return e


class Fila(QWidget):
    """Título (y detalle opcional) a la izquierda, control a la derecha."""

    def __init__(self, titulo, detalle="", control=None):
        super().__init__()
        diseno = QHBoxLayout(self)
        diseno.setContentsMargins(14, 10, 14, 10)
        diseno.setSpacing(12)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.titulo = etiqueta(titulo)
        textos.addWidget(self.titulo)
        self.detalle = etiqueta(detalle, "secundario", envolver=True)
        self.detalle.setVisible(bool(detalle))
        textos.addWidget(self.detalle)
        diseno.addLayout(textos, 1)
        if control is not None:
            diseno.addWidget(control, 0, Qt.AlignVCenter)

    def fijar_detalle(self, texto):
        self.detalle.setText(texto)
        self.detalle.setVisible(bool(texto))


def grupo(*filas, titulo=None):
    """Tarjeta redondeada con filas separadas por líneas finas."""
    contenedor = QWidget()
    externo = QVBoxLayout(contenedor)
    externo.setContentsMargins(0, 0, 0, 0)
    externo.setSpacing(6)
    if titulo:
        cabecera = etiqueta(titulo, "secundario")
        cabecera.setContentsMargins(6, 0, 0, 0)
        externo.addWidget(cabecera)
    tarjeta = QFrame()
    tarjeta.setObjectName("grupo")
    interno = QVBoxLayout(tarjeta)
    interno.setContentsMargins(0, 2, 0, 2)
    interno.setSpacing(0)
    for i, fila in enumerate(filas):
        if i:
            linea = QFrame()
            linea.setObjectName("linea")
            interno.addWidget(linea)
        interno.addWidget(fila)
    externo.addWidget(tarjeta)
    return contenedor
