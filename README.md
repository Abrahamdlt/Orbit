# Orbit

Pequeñas herramientas (plugins) que viven junto al reloj de Windows, con un diseño limpio inspirado en macOS.

Haz clic en el icono de Orbit en la bandeja del sistema y verás tus plugins: cada uno se enciende con un
interruptor, tiene su propio atajo de teclado y sus ajustes en una barra lateral.

## Plugins

| Plugin | Qué hace | Atajo por defecto |
|---|---|---|
| **Rueda radial** | Arrastra un archivo o carpeta en el Explorador y pulsa **Tab**: aparece una rueda para comprimir (ZIP, RAR, 7z), convertir (Word, Excel y PowerPoint a PDF, imágenes a PNG/JPG/WEBP/ICO/PDF) o extraer. | Ctrl + Alt + Shift + R |
| **Medidor FPS** | Una pastilla discreta encima de cualquier ventana o juego con FPS, uso y temperatura de CPU y GPU, y uso de RAM. | Ctrl + Alt + Shift + F |
| **Texto de pantalla** | Eliges un área de la pantalla y su texto se copia al portapapeles, aunque sea una imagen, un PDF escaneado o un video. Usa el reconocimiento de texto de Windows, sin internet. | Ctrl + Alt + Shift + T |
| **Historial del portapapeles** | Recuerda lo último que copias (texto e imágenes). El atajo abre una lista con buscador junto al cursor; al elegir, lo pega donde estabas. | Ctrl + Alt + Shift + V |
| **Cambio de audio** | Pasa a la siguiente de tus salidas favoritas (audífonos, parlantes...) sin abrir la configuración de sonido. | Ctrl + Alt + Shift + A |
| **Siempre encima** | Fija la ventana que tienes delante por encima de las demás, con un borde de color. El mismo atajo la suelta. | Ctrl + Alt + Shift + P |
| **Mantener despierto** | El equipo no se suspende (ni apaga la pantalla, si quieres) durante 30 min, 1 h, 2 h o hasta que lo apagues. | Ctrl + Alt + Shift + D |
| **Cuentagotas** | Una lupa para copiar el color de cualquier píxel en HEX, RGB o HSL. Guarda los últimos 12 colores. | Ctrl + Alt + Shift + C |
| **Pomodoro** | Una pastilla con la cuenta atrás de enfoque y descanso; avisa en cada cambio de fase. | Ctrl + Alt + Shift + O |

Los atajos se cambian en *Ajustes*, y Orbit avisa si otro programa ya usa la combinación.

### Rendimiento

- **Modo bajo consumo** (*Ajustes → General*): sin animaciones ni efecto vidrio (tampoco en la lista del portapapeles
  ni en las pastillas), el Medidor FPS se actualiza cada 2 segundos, el borde de Siempre encima sigue a la ventana
  con menos frecuencia y la ventana de Ajustes se libera de la memoria al cerrarla.
- **Plugins nuevos de la 1.2**: en reposo apenas ocupan memoria (unos 2 MB los siete). El Texto de pantalla y el
  Cambio de audio cargan sus librerías de Windows solo la primera vez que los usas.
- **Temperaturas** (*Medidor FPS*): apagarlas ahorra unos 100 MB, porque el ayudante ya no carga los sensores.
- **Baja latencia** (*Medidor FPS*): el FPS se actualiza 4 veces por segundo y reacciona al instante a los tirones.

## Descargar e instalar

1. Descarga **Orbit.exe** desde [Releases](../../releases/latest).
2. Ábrelo: se abre el instalador. Elige qué plugins quieres y listo.

No hace falta instalar Python ni nada más. Se instala solo para tu usuario.

### Avisos normales

- **«Windows protegió tu PC»**: Orbit no tiene una firma digital de pago, así que Windows o el antivirus pueden
  avisar. Pulsa *Más información* → *Ejecutar de todas formas*.
- **Permiso de administrador (solo Medidor FPS)**: contar los FPS de otros programas y leer la temperatura de la
  CPU requiere permiso de administrador. Se pide una vez, al instalar o al añadir el plugin. El ayudante corre
  como una tarea programada que solo lee datos. El resto de plugins no lo necesita.
- **Ventanas de administrador**: Windows no deja que un programa normal les escriba. Siempre encima no puede fijarlas
  y el Historial del portapapeles solo copia (lo pegas tú con Ctrl+V).
- **Idiomas del Texto de pantalla**: lee los idiomas de reconocimiento de texto que tenga Windows. Para añadir uno:
  *Configuración → Hora e idioma → Idioma y región → Opciones de idioma → Reconocimiento óptico de caracteres*.
- **Pantalla completa exclusiva**: en ese modo Windows no deja dibujar nada encima de un juego. Usa *ventana sin
  bordes*.
- **Office**: las conversiones de Word, Excel y PowerPoint aparecen solo si el equipo tiene Microsoft Office.

### Privacidad

Orbit no se conecta a internet ni envía datos. Los datos del Medidor FPS viajan solo dentro del equipo
(127.0.0.1) y el Texto de pantalla lee la imagen con el OCR de Windows, sin salir del equipo. Los ajustes se guardan
en `%APPDATA%\Orbit`.

El **Historial del portapapeles** viene sin marcar en el instalador. Guarda lo que copias solo en memoria (se olvida
al cerrar Orbit) salvo que actives *Recordar al reiniciar*, que lo guarda sin cifrar en `%APPDATA%\Orbit`. Lo que
copian los gestores de contraseñas no se guarda nunca: Orbit respeta los formatos con los que piden no aparecer en
historiales (`ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory` y
`Clipboard Viewer Ignore`).

## Desarrollo

```bash
pip install -r requirements.txt
pythonw orbit.pyw          # abre Orbit desde el código
pip install pyinstaller
python construir.py        # crea dist/Orbit.exe (descarga las herramientas de terceros a vendor/)
dist\Orbit.exe --probar-modulos   # sale con 0 si el .exe trae todo lo que cargan los plugins
```

Estructura:

```
orbit/
  app.py          icono de la bandeja, plugins, atajos
  panel.py        panel de la bandeja
  ajustes.py      ventana de ajustes con barra lateral
  instalador.py   instalador con lista de plugins
  ayudante.py     registro del ayudante con permisos de administrador
  estilo.py       colores, controles, iconos, vidrio y animaciones
  pantalla.py     selector de pantalla (elegir un área o un píxel con lupa)
  pastilla.py     pastilla flotante en una esquina (Medidor FPS y Pomodoro)
  plugins/
    __init__.py   lista de plugins (CLASES)
    radial/       Rueda radial
    fps/          Medidor FPS (overlay, sensores y medición)
    ocr/          Texto de pantalla (OCR de Windows con winrt)
    portapapeles/ Historial del portapapeles (historial, lista y pegado)
    audio/        Cambio de audio (pycaw + IPolicyConfig)
    encima/       Siempre encima
    despierto/    Mantener despierto
    color/        Cuentagotas
    pomodoro/     Pomodoro (temporizador sin Qt y pastilla)
```

Para crear un plugin nuevo: hereda de `orbit.plugins.base.Plugin`, implementa `iniciar`, `detener` y
`grupos_ajustes` (y `al_atajo` si su atajo hace algo distinto de activarlo o desactivarlo), pon sus valores por
defecto en `config.DEFECTO` y añádelo a `CLASES` en `orbit/plugins/__init__.py`. El panel, los ajustes y el
instalador lo toman de ahí.

## Software de terceros

Orbit.exe incluye estas herramientas, cada una con su propia licencia:

- [PresentMon](https://github.com/GameTechDev/PresentMon) (Intel, MIT): lectura de FPS.
- [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) (MPL 2.0): temperaturas.
- [PawnIO](https://pawnio.eu) (namazso): driver firmado que LibreHardwareMonitor usa para leer la CPU. Solo se
  instala si lo eliges.
- [Qt / PySide6](https://www.qt.io/qt-for-python) (LGPL), [psutil](https://github.com/giampaolo/psutil),
  [pywin32](https://github.com/mhammond/pywin32), [Pillow](https://python-pillow.org),
  [pythonnet](https://github.com/pythonnet/pythonnet), [nvidia-ml-py](https://pypi.org/project/nvidia-ml-py/).
- [pycaw](https://github.com/AndreMiras/pycaw) (MIT) y [comtypes](https://github.com/enthought/comtypes) (MIT):
  salidas de audio.
- [pywinrt](https://github.com/pywinrt/pywinrt) (MIT): acceso al OCR de Windows (`Windows.Media.Ocr`).
