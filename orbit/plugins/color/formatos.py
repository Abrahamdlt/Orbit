"""Cómo se escribe un color al copiarlo: HEX, RGB o HSL (sin Qt, para poder probarlo)."""
import colorsys

FORMATOS = ["hex", "rgb", "hsl"]
NOMBRES = ["HEX", "RGB", "HSL"]


def a_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"


def desde_hex(texto):
    texto = texto.lstrip("#")
    return int(texto[0:2], 16), int(texto[2:4], 16), int(texto[4:6], 16)


def a_hsl(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return round(h * 360) % 360, round(s * 100), round(l * 100)


def escribir(r, g, b, formato):
    if formato == "rgb":
        return f"rgb({r}, {g}, {b})"
    if formato == "hsl":
        return "hsl({}, {}%, {}%)".format(*a_hsl(r, g, b))
    return a_hex(r, g, b)
