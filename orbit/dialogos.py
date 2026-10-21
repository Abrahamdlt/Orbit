"""Ventanitas de Orbit: elegir un atajo, elegir una tecla y confirmar acciones."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from . import estilo, sistema
from .atajos import texto_atajo
from .config import MOD_ALT, MOD_CTRL, MOD_SHIFT

MODIFICADORES_VK = {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}


class DialogoBase(QDialog):
    def __init__(self, titulo, ancho=400):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.paleta = estilo.paleta()
        self.setWindowTitle(titulo)
        self.setWindowIcon(estilo.icono_orbit())
        self.setFixedWidth(ancho)
        self.setStyleSheet(estilo.hoja_de_estilo(self.paleta) + f"QDialog {{ background: {self.paleta.fondo}; }}")
        sistema.barra_de_titulo_oscura(int(self.winId()), self.paleta.oscuro)
        self.diseno = QVBoxLayout(self)
        self.diseno.setContentsMargins(26, 22, 26, 20)
        self.diseno.setSpacing(10)

    def botones(self, *botones):
        fila = QHBoxLayout()
        fila.addStretch()
        for b in botones:
            fila.addWidget(b)
        self.diseno.addSpacing(6)
        self.diseno.addLayout(fila)

    # TAB no llega a keyPressEvent: Qt lo usa para mover el foco entre controles
    def event(self, evento):
        if evento.type() == QEvent.KeyPress and evento.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            self.keyPressEvent(evento)
            return True
        return super().event(evento)


def _tecla_grande():
    e = QLabel()
    e.setAlignment(Qt.AlignCenter)
    e.setFont(estilo.fuente(15, QFont.DemiBold, titulo=True))
    e.setMinimumHeight(56)
    return e


class DialogoAtajo(DialogoBase):
    """Pide una combinación tipo Ctrl + Alt + Shift + F y comprueba que no la use nadie más."""

    def __init__(self, nombre_plugin, actual, atajos):
        super().__init__(f"Atajo de {nombre_plugin}")
        self.atajos, self.actual, self.resultado = atajos, actual, None
        titulo = QLabel("Pulsa la nueva combinación")
        titulo.setObjectName("subtitulo")
        self.vista = _tecla_grande()
        self.vista.setText(actual["texto"])
        self.vista.setStyleSheet(f"background: {self.paleta.superficie}; border-radius: 12px;"
                                 f"border: 1px solid {self.paleta.separador};")
        self.aviso = QLabel("Usa al menos dos de Ctrl, Alt y Shift, más una letra, número o tecla F.")
        self.aviso.setObjectName("secundario")
        self.aviso.setWordWrap(True)
        self.cancelar, self.guardar = estilo.boton("Cancelar"), estilo.boton("Guardar", "primario")
        self.guardar.setEnabled(False)
        self.cancelar.clicked.connect(self.reject)
        self.guardar.clicked.connect(self.accept)
        for b in (self.cancelar, self.guardar):
            b.setFocusPolicy(Qt.NoFocus)
        for w in (titulo, self.vista, self.aviso):
            self.diseno.addWidget(w)
        self.botones(self.cancelar, self.guardar)

    def keyPressEvent(self, evento):
        vk = evento.nativeVirtualKey()
        if vk == 0x1B:
            self.reject()
            return
        q = evento.modifiers()
        mods = (MOD_CTRL if q & Qt.ControlModifier else 0) | (MOD_ALT if q & Qt.AltModifier else 0) \
            | (MOD_SHIFT if q & Qt.ShiftModifier else 0)
        if vk in MODIFICADORES_VK or not vk:
            partes = [n for m, n in ((MOD_CTRL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift")) if mods & m]
            self.vista.setText(" + ".join(partes + ["…"]))
            return
        texto = texto_atajo(mods, vk)
        self.vista.setText(texto)
        self.guardar.setEnabled(False)
        self.aviso.setStyleSheet(f"color: {self.paleta.rojo};")
        if q & Qt.MetaModifier:
            self.aviso.setText("La tecla Windows está reservada para atajos del sistema.")
        elif bin(mods).count("1") < 2:
            self.aviso.setText("Usa al menos dos de Ctrl, Alt y Shift para que no choque con otros programas.")
        elif (mods, vk) != (self.actual["mods"], self.actual["vk"]) and not self.atajos.libre(mods, vk):
            self.aviso.setText("Ese atajo ya lo usa Windows u otro programa. Prueba con otro.")
        else:
            self.aviso.setStyleSheet(f"color: {self.paleta.verde};")
            self.aviso.setText("Libre: no choca con nada.")
            self.resultado = {"mods": mods, "vk": vk, "texto": texto}
            self.guardar.setEnabled(True)


class DialogoTecla(DialogoBase):
    """Pide una sola tecla (la que abre la rueda mientras arrastras)."""

    def __init__(self, actual):
        super().__init__("Tecla de la rueda")
        self.vk, self.nombre = None, None
        titulo = QLabel("Pulsa la tecla que quieres usar")
        titulo.setObjectName("subtitulo")
        vista = _tecla_grande()
        vista.setText(actual)
        vista.setStyleSheet(f"background: {self.paleta.superficie}; border-radius: 12px;"
                            f"border: 1px solid {self.paleta.separador};")
        aviso = QLabel("Solo se usa mientras arrastras algo en el Explorador; el resto del tiempo funciona normal. "
                       "Esc para cancelar.")
        aviso.setObjectName("secundario")
        aviso.setWordWrap(True)
        for w in (titulo, vista, aviso):
            self.diseno.addWidget(w)

    def keyPressEvent(self, evento):
        vk = evento.nativeVirtualKey()
        if vk == 0x1B:
            self.reject()
            return
        if not vk or vk in MODIFICADORES_VK:
            return
        self.vk = vk
        self.nombre = QKeySequence(evento.key()).toString(QKeySequence.NativeText) or f"Tecla {vk}"
        self.accept()


def confirmar(titulo, texto, aceptar="Aceptar", peligro=False):
    d = DialogoBase(titulo, 420)
    encabezado = QLabel(titulo)
    encabezado.setObjectName("subtitulo")
    cuerpo = QLabel(texto)
    cuerpo.setWordWrap(True)
    cuerpo.setObjectName("secundario")
    d.diseno.addWidget(encabezado)
    d.diseno.addWidget(cuerpo)
    no, si = estilo.boton("Cancelar"), estilo.boton(aceptar, "primario")
    if peligro:
        si.setStyleSheet(f"background: {d.paleta.rojo}; color: white;")
    no.clicked.connect(d.reject)
    si.clicked.connect(d.accept)
    d.botones(no, si)
    return d.exec() == QDialog.Accepted


def informar(titulo, texto):
    d = DialogoBase(titulo, 420)
    encabezado = QLabel(titulo)
    encabezado.setObjectName("subtitulo")
    cuerpo = QLabel(texto)
    cuerpo.setWordWrap(True)
    cuerpo.setObjectName("secundario")
    d.diseno.addWidget(encabezado)
    d.diseno.addWidget(cuerpo)
    ok = estilo.boton("Entendido", "primario")
    ok.clicked.connect(d.accept)
    d.botones(ok)
    d.exec()
