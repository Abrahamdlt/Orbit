# Orbit

Pequeñas herramientas (plugins) que viven junto al reloj de Windows, con un diseño limpio inspirado en macOS.

Haz clic en el icono de Orbit en la bandeja del sistema y verás tus plugins: cada uno se enciende con un
interruptor, tiene su propio atajo de teclado y sus ajustes en una barra lateral.

## Plugins

| Plugin | Qué hace | Atajo por defecto |
|---|---|---|
| **Rueda radial** | Arrastra un archivo o carpeta en el Explorador y pulsa **Tab**: aparece una rueda para comprimir (ZIP, RAR, 7z), convertir (Word, Excel y PowerPoint a PDF, imágenes a PNG/JPG/WEBP/ICO/PDF) o extraer. | Ctrl + Alt + Shift + R |
| **Medidor FPS** | Una pastilla discreta encima de cualquier ventana o juego con FPS, uso y temperatura de CPU y GPU, y uso de RAM. | Ctrl + Alt + Shift + F |

## Descargar e instalar

1. Descarga **Orbit.exe** desde [Releases](../../releases/latest).
2. Ábrelo: se abre el instalador. Elige qué plugins quieres y listo.

No hace falta instalar Python ni nada más. Se instala solo para tu usuario.

### Avisos normales

- **«Windows protegió tu PC»**: Orbit no tiene una firma digital de pago, así que Windows o el antivirus pueden
  avisar. Pulsa *Más información* → *Ejecutar de todas formas*.
- **Permiso de administrador (solo Medidor FPS)**: contar los FPS de otros programas y leer la temperatura de la
  CPU requiere permiso de administrador. Se pide una vez, al instalar o al añadir el plugin. El ayudante corre
  como una tarea programada que solo lee datos.
- **Pantalla completa exclusiva**: en ese modo Windows no deja dibujar nada encima de un juego. Usa *ventana sin
  bordes*.
- **Office**: las conversiones de Word, Excel y PowerPoint aparecen solo si el equipo tiene Microsoft Office.

### Privacidad

Orbit no se conecta a internet ni envía datos. Los datos del Medidor FPS viajan solo dentro del equipo
(127.0.0.1). Los ajustes se guardan en `%APPDATA%\Orbit`.

## Desarrollo

```bash
pip install -r requirements.txt
pythonw orbit.pyw          # abre Orbit desde el código
pip install pyinstaller
python construir.py        # crea dist/Orbit.exe (descarga las herramientas de terceros a vendor/)
```

Estructura:

```
orbit/
  app.py          icono de la bandeja, plugins, atajos
  panel.py        panel de la bandeja
  ajustes.py      ventana de ajustes con barra lateral
  instalador.py   instalador con lista de plugins
  ayudante.py     registro del ayudante con permisos de administrador
  estilo.py       colores, controles y animaciones
  plugins/
    radial/       Rueda radial
    fps/          Medidor FPS (overlay, sensores y medición)
```

Para crear un plugin nuevo: hereda de `orbit.plugins.base.Plugin`, implementa `iniciar`, `detener` y
`grupos_ajustes`, y añádelo a la lista de `orbit/app.py` y a `PLUGINS` en `orbit/instalador.py`.

## Software de terceros

Orbit.exe incluye estas herramientas, cada una con su propia licencia:

- [PresentMon](https://github.com/GameTechDev/PresentMon) (Intel, MIT): lectura de FPS.
- [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) (MPL 2.0): temperaturas.
- [PawnIO](https://pawnio.eu) (namazso): driver firmado que LibreHardwareMonitor usa para leer la CPU. Solo se
  instala si lo eliges.
- [Qt / PySide6](https://www.qt.io/qt-for-python) (LGPL), [psutil](https://github.com/giampaolo/psutil),
  [pywin32](https://github.com/mhammond/pywin32), [Pillow](https://python-pillow.org),
  [pythonnet](https://github.com/pythonnet/pythonnet), [nvidia-ml-py](https://pypi.org/project/nvidia-ml-py/).
