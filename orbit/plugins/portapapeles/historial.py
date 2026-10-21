"""El historial del portapapeles, sin Qt: repetidos, máximo, fijados y la regla de privacidad."""
import base64
import ntpath
import re
import time

MAXIMO_IMAGENES = 8  # las imágenes pesan: más allá de estas, se van las más viejas sin fijar
# Formatos con los que los gestores de contraseñas (y Windows) piden que no se guarde lo copiado
EXCLUIR = "ExcludeClipboardContentFromMonitorProcessing"
IGNORAR = "Clipboard Viewer Ignore"
PERMITIR_HISTORIAL = "CanIncludeInClipboardHistory"  # un DWORD: 0 = no guardarlo


def nombre_formato(formato):
    """Qt nombra los formatos propios de Windows como application/x-qt-windows-mime;value="Nombre"."""
    encontrado = re.search(r'value="([^"]+)"', formato)
    return encontrado.group(1) if encontrado else formato


def es_privado(formatos, leer):
    """True si lo copiado no debe guardarse. leer(formato) devuelve los bytes de ese formato."""
    for formato in formatos:
        nombre = nombre_formato(formato)
        if nombre in (EXCLUIR, IGNORAR):
            return True
        if nombre == PERMITIR_HISTORIAL:
            datos = leer(formato)
            if len(datos) >= 4 and int.from_bytes(bytes(datos[:4]), "little") == 0:
                return True
    return False


class Historial:
    def __init__(self, maximo=30):
        self.maximo = maximo
        self.elementos = []  # el más reciente primero; cada uno es un dict (ver texto() e imagen())

    @staticmethod
    def texto(texto, clave, hora=None):
        return {"tipo": "texto", "texto": texto, "clave": clave, "fijado": False, "hora": hora or time.time()}

    @staticmethod
    def imagen(png, mini, ancho, alto, clave, hora=None):
        """png: la imagen entera; mini: una miniatura pequeña para la lista (también en PNG)."""
        return {"tipo": "imagen", "png": png, "mini": mini, "ancho": ancho, "alto": alto, "clave": clave,
                "fijado": False, "hora": hora or time.time()}

    @staticmethod
    def archivos(rutas, clave, hora=None):
        """Archivos o carpetas copiados (en el Explorador, por ejemplo): se guardan sus rutas, no su contenido."""
        return {"tipo": "archivos", "rutas": list(rutas), "clave": clave, "fijado": False, "hora": hora or time.time()}

    def buscar_clave(self, clave):
        return next((e for e in self.elementos if e["clave"] == clave), None)

    def agregar(self, elemento):
        """Lo pone arriba. Si ya estaba, lo sube en vez de duplicarlo (y sigue fijado si lo estaba)."""
        anterior = self.buscar_clave(elemento["clave"])
        if anterior:
            self.elementos.remove(anterior)
            elemento["fijado"] = anterior["fijado"]
        self.elementos.insert(0, elemento)
        self._recortar()

    def quitar(self, clave):
        self.elementos = [e for e in self.elementos if e["clave"] != clave]

    def fijar(self, clave, fijado):
        elemento = self.buscar_clave(clave)
        if elemento:
            elemento["fijado"] = fijado

    def limpiar(self):
        """Borra todo menos lo fijado."""
        self.elementos = [e for e in self.elementos if e["fijado"]]

    def fijar_maximo(self, maximo):
        self.maximo = maximo
        self._recortar()

    def _recortar(self):
        imagenes = [e for e in self.elementos if e["tipo"] == "imagen" and not e["fijado"]]
        for sobrante in imagenes[MAXIMO_IMAGENES:]:
            self.elementos.remove(sobrante)
        sueltos = [e for e in self.elementos if not e["fijado"]]
        while len(self.elementos) > self.maximo and sueltos:
            self.elementos.remove(sueltos.pop())  # el más viejo sin fijar

    def ordenados(self, busqueda=""):
        """Los fijados primero; dentro de cada grupo, el más reciente primero. Filtra por texto si se busca."""
        busqueda = busqueda.casefold().strip()
        lista = [e for e in self.elementos if not busqueda
                 or (e["tipo"] == "texto" and busqueda in e["texto"].casefold())
                 or (e["tipo"] == "imagen" and busqueda in "imagen")
                 or (e["tipo"] == "archivos" and any(busqueda in ntpath.basename(r).casefold() for r in e["rutas"]))]
        return [e for e in lista if e["fijado"]] + [e for e in lista if not e["fijado"]]

    # --- guardar en disco («Recordar al reiniciar»)
    def a_datos(self):
        datos = []
        for e in self.elementos:
            copia = dict(e)
            if e["tipo"] == "imagen":
                for campo in ("png", "mini"):
                    copia[campo] = base64.b64encode(e[campo]).decode("ascii")
            datos.append(copia)
        return datos

    def desde_datos(self, datos):
        self.elementos = []
        for e in datos:
            if e.get("tipo") == "imagen":
                e = dict(e, png=base64.b64decode(e["png"]), mini=base64.b64decode(e["mini"]))
            elif e.get("tipo") not in ("texto", "archivos"):
                continue
            self.elementos.append(e)
        self._recortar()
