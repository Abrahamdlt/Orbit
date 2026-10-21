"""Salidas de audio de Windows: cuáles hay, cuál es la predeterminada y cómo cambiarla.

Se listan con pycaw (MMDevice). Para cambiar la predeterminada se usa la interfaz COM IPolicyConfig, la misma que
SoundSwitch y EarTrumpet: Microsoft no la documenta, pero no ha cambiado desde Windows Vista. Si un día falla,
el plugin avisa en vez de romperse. comtypes y pycaw se cargan solo al usar el plugin.
"""
NOMBRE = ("{A45C254E-DF1C-4EFD-8020-67D146A850E0}", 14)  # PKEY_Device_FriendlyName
SALIDA, ACTIVO = 0, 0x1                                   # eRender, DEVICE_STATE_ACTIVE
CONSOLA, MULTIMEDIA, COMUNICACIONES = 0, 1, 2            # roles de Windows


def _enumerador():
    from pycaw.utils import AudioUtilities
    return AudioUtilities.GetDeviceEnumerator()


def _nombre(dispositivo):
    from comtypes import GUID
    from pycaw.api.mmdeviceapi import PROPERTYKEY
    clave = PROPERTYKEY()
    clave.fmtid, clave.pid = GUID(NOMBRE[0]), NOMBRE[1]
    valor = dispositivo.OpenPropertyStore(0).GetValue(clave)  # STGM_READ
    try:
        return valor.GetValue() or "Sin nombre"
    finally:
        valor.clear()


def salidas():
    """[(id, nombre)] de las salidas conectadas ahora."""
    coleccion = _enumerador().EnumAudioEndpoints(SALIDA, ACTIVO)
    lista = []
    for i in range(coleccion.GetCount()):
        dispositivo = coleccion.Item(i)
        lista.append((dispositivo.GetId(), _nombre(dispositivo)))
    return lista


def _predeterminada():
    try:
        return _enumerador().GetDefaultAudioEndpoint(SALIDA, MULTIMEDIA)
    except Exception:  # sin ninguna salida, Windows responde con un error (E_NOTFOUND)
        return None


def predeterminada():
    """id de la salida predeterminada, o None si no hay ninguna."""
    dispositivo = _predeterminada()
    return dispositivo.GetId() if dispositivo else None


def nombre_predeterminada():
    dispositivo = _predeterminada()
    return _nombre(dispositivo) if dispositivo else None


def fijar(id_dispositivo):
    """La vuelve predeterminada para todo: juegos y música, videollamadas y sonidos del sistema."""
    import comtypes
    from pycaw.api.policyconfig import IPolicyConfig
    from pycaw.constants import CLSID_CPolicyConfigClient
    politica = comtypes.CoCreateInstance(CLSID_CPolicyConfigClient, IPolicyConfig, comtypes.CLSCTX_ALL)
    for rol in (CONSOLA, MULTIMEDIA, COMUNICACIONES):
        politica.SetDefaultEndpoint(id_dispositivo, rol)
