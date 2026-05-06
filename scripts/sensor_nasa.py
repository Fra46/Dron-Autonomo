import random
import socket
import json
import time
import itertools
import earthaccess
import h5py
import numpy as np
import os
import glob
import sys
import concurrent.futures

DESTINO_IP     = "127.0.0.1"
DESTINO_PUERTO = 5005

# ────────────────────────────────────────────────────────────────────────────
# AUTENTICACIÓN CON NASA - VERSIÓN ROBUSTA
# ────────────────────────────────────────────────────────────────────────────

USE_MOCK_MODE = False  # Se activará si falla conexión a NASA

print("🌍 Conectando con NASA SMAP...")
print()

# EarthAccess usa `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` o `EARTHDATA_TOKEN`.
# Permitimos también alias comunes para facilitar la configuración.
def sync_earthdata_env_vars():
    env = os.environ
    if env.get("EARTHACCESS_USERNAME") and env.get("EARTHACCESS_PASSWORD"):
        os.environ.setdefault("EARTHDATA_USERNAME", env["EARTHACCESS_USERNAME"])
        os.environ.setdefault("EARTHDATA_PASSWORD", env["EARTHACCESS_PASSWORD"])
    if env.get("EARTHACCESS_TOKEN"):
        os.environ.setdefault("EARTHDATA_TOKEN", env["EARTHACCESS_TOKEN"])

sync_earthdata_env_vars()

try:
    # Intenta login con credenciales de entorno o archivo .netrc
    auth = earthaccess.login(strategy="environment")
    if not auth:
        print("⚠️ Variables de entorno no configuradas. Intentando interactivo...")

        def interactive_login():
            return earthaccess.login(strategy="interactive")

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(interactive_login)
            try:
                auth = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                raise TimeoutError("Timeout en autenticación interactiva (30s)")

    if auth:
        print("✅ Conexión exitosa con NASA\n")
    else:
        raise RuntimeError("No se pudo autenticar con NASA")

except (TimeoutError, EOFError, KeyboardInterrupt, RuntimeError) as e:
    print(f"\n❌ Error de autenticación NASA: {e}")
    print("📊 Cambiando a modo simulación con datos mock...\n")
    USE_MOCK_MODE = True
except Exception as e:
    print(f"\n❌ Error inesperado: {e}")
    print("📊 Cambiando a modo simulación con datos mock...\n")
    USE_MOCK_MODE = True

# Busca datos del satélite SMAP 
print("🛰️ Buscando datos de humedad del suelo (SMAP)")

if not USE_MOCK_MODE:
    try:
        resultados = earthaccess.search_data(
            # Usamos el satelite que se encarga de medir la humedad del suelo: SMAP
            short_name="SPL3SMP",
            # Solo archivos que cubran el área del Cesar
            bounding_box=(-74, 9, -72, 11),
            # Solo archivos en este rango de fechas
            temporal=("2024-06-01", "2024-06-03")
        )
    except Exception as e:
        print(f"❌ Error en búsqueda SMAP: {e}")
        print("📊 Cambiando a modo simulación...\n")
        USE_MOCK_MODE = True
        resultados = []
else:
    resultados = []

# Descarga el primer archivo encontrado para obtener los datos reales.
print(f"📁 Archivos encontrados: {len(resultados)}")

archivos_locales = glob.glob("SMAP_L3_SM_P_*.h5")

if len(archivos_locales) > 0:
    print(f"✅ Archivos ya descargados ({len(archivos_locales)} encontrados)")
    archivos = archivos_locales
elif len(resultados) > 0 and not USE_MOCK_MODE:
    print("⏬ Descargando datos...")
    try:
        archivos = earthaccess.download(resultados, local_path=".")
    except Exception as e:
        print(f"❌ Error en descarga: {e}")
        print("📊 Usando modo simulación...\n")
        USE_MOCK_MODE = True
        archivos = []
else:
    archivos = []


print("\n📊 Procesando datos de humedad del suelo para la región del Cesar\n")

# Definir límites geográficos del Cesar para filtrar los datos
LAT_MIN, LAT_MAX =  9.0, 11.0
LON_MIN, LON_MAX = -74.0, -72.0

valores_reales = []
valores_sur = []
valores_centro = []
valores_norte = []

# ── Modo Real (NASA SMAP) ──────────────────────────────────────────────────
if len(archivos) > 0 and not USE_MOCK_MODE:
    print("🔍 Extrayendo datos reales del satélite NASA SMAP...\n")
    
    try:
        # Recorrer cada archivo descargado, para extraer los datos de humedad y sus coordenadas, y filtrar solo los que estén dentro del Cesar.
        for archivo in archivos:
            with h5py.File(archivo, "r") as f:

                # Extraemos humedad y coordenadas
                humedad_raw = f["Soil_Moisture_Retrieval_Data_AM"]["soil_moisture"][:]
                latitudes   = f["Soil_Moisture_Retrieval_Data_AM"]["latitude"][:]
                longitudes  = f["Soil_Moisture_Retrieval_Data_AM"]["longitude"][:]

                # Recorrer cada píxel del satélite
                filas, columnas = humedad_raw.shape
                for i in range(filas):
                    for j in range(columnas):
                        lat = latitudes[i, j]
                        lon = longitudes[i, j]
                        hum = humedad_raw[i, j]

                        # Filtramos solo los píxeles dentro del Cesar
                        if (LAT_MIN <= lat <= LAT_MAX and
                            LON_MIN <= lon <= LON_MAX and
                            hum > 0):

                            # Convertimos a porcentaje y redondeamos a 1 decimal
                            valor = round(float(hum) * 100, 1)
                            valores_reales.append(valor)

                            # Asignar zona geográfica real según latitud
                            if lat < 9.66:
                                valores_sur.append(valor)
                            elif lat < 10.33:
                                valores_centro.append(valor)
                            else:
                                valores_norte.append(valor)

    except Exception as e:
        print(f"❌ Error extrayendo datos: {e}")
        print("📊 Cambiando a modo simulación...\n")
        USE_MOCK_MODE = True
        valores_reales = []
        valores_sur = []
        valores_centro = []
        valores_norte = []

# ── Modo Simulación (si NASA falló o no hay datos) ────────────────────────
if USE_MOCK_MODE or len(valores_reales) == 0:
    print("🤖 Generando datos simulados basados en parámetros reales...\n")
    
    # Generar datos simulados realistas para Cesar
    # Humedad típica en región tropical: 30-80%
    np.random.seed(42)  # Para reproducibilidad
    valores_reales = list(np.random.uniform(30, 80, 50).round(1))
    valores_sur = valores_reales[:17]
    valores_centro = valores_reales[17:34]
    valores_norte = valores_reales[34:]
    USE_MOCK_MODE = True

print(f"✅ Valores extraídos: {len(valores_reales)}")

# Confirmamos que se encontraron datos válidos para la región del Cesar
if len(valores_reales) == 0:
    print("\n❌ No se encontraron valores válidos.")
    print("⚠️ El sistema necesita datos. Reinicia con conexión a Internet o verifica credenciales NASA.")
    sys.exit(1)

# Guardar mínimo y máximo para calcular estados relativos
humedad_minima  = min(valores_reales)
humedad_maxima  = max(valores_reales)
humedad_promedio = round(sum(valores_reales) / len(valores_reales), 1)

# Mostramos resumen de los datos obtenidos
print(f"📈 Estadísticas:")
print(f"   Mínima:   {humedad_minima}%")
print(f"   Máxima:   {humedad_maxima}%")
print(f"   Promedio: {humedad_promedio}%")
print(f"   Modo:     {'🤖 SIMULACIÓN' if USE_MOCK_MODE else '🛰️ NASA SMAP REAL'}\n")

# Si alguna zona no tiene datos reales, repartimos por tercio como fallback
if not valores_sur or not valores_centro or not valores_norte:
    print("⚠️ Algunas zonas no tienen datos reales suficientes. Reasignando por niveles de humedad...")
    valores_reales.sort()
    total = len(valores_reales)
    tercio = total // 3
    valores_sur = valores_reales[:tercio]
    valores_centro = valores_reales[tercio:tercio * 2]
    valores_norte = valores_reales[tercio * 2:]
else:
    total = len(valores_reales)

print(f"Total: {total}")
print(f"Sur: {len(valores_sur)}")
print(f"Centro: {len(valores_centro)}")
print(f"Norte: {len(valores_norte)}")

paquetes = []
for sur_val, centro_val, norte_val in itertools.zip_longest(valores_sur, valores_centro, valores_norte):
    if sur_val is not None:
        paquetes.append({"zona": "sur", "humedad": sur_val})
    if centro_val is not None:
        paquetes.append({"zona": "centro", "humedad": centro_val})
    if norte_val is not None:
        paquetes.append({"zona": "norte", "humedad": norte_val})

# Usamos itertools.cycle(), cuando se acaben los datos reales,
# vuelve a empezar desde el primero
ciclo_paquetes = itertools.cycle(paquetes)

print(f"📍 Distribución de valores por zona:")
print(f"   Sur:    {len(valores_sur):>3} valores | {min(valores_sur):>5}% a {max(valores_sur):>5}%")
print(f"   Centro: {len(valores_centro):>3} valores | {min(valores_centro):>5}% a {max(valores_centro):>5}%")
print(f"   Norte:  {len(valores_norte):>3} valores | {min(valores_norte):>5}% a {max(valores_norte):>5}%\n")

# Creamos el socket UDP para enviar los datos al dron de riego.
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Interpretar el nivel de humedad para determinar el estado del suelo
def interpretar_humedad(humedad):

    if humedad >= 70:
        return "humedo"       # tercio más alto → sin riego
    elif humedad >= 50:
        return "normal"       # tercio medio    → monitorear
    elif humedad >= 30:
        return "seco"         # parte baja      → considerar riego
    else:
        return "muy_seco" 
    
print("🚀 INICIANDO TRANSMISIÓN DE DATOS")
print("=" * 70)
print(f"📡 Destino: {DESTINO_IP}:{DESTINO_PUERTO}")
print(f"🛰️ Fuente:  {'🤖 SIMULACIÓN' if USE_MOCK_MODE else '🛰️ NASA SMAP REAL'}")
print("=" * 70)
print()

try:
    while True:
        paquete = next(ciclo_paquetes)

        datos = {
            "zona"        : paquete["zona"],
            "humedad"     : paquete["humedad"],
            "estado_suelo": interpretar_humedad(paquete["humedad"]),
            "temperatura" : round(random.uniform(28.0, 38.0), 1), 
        }

        mensaje = json.dumps(datos).encode()
        sock.sendto(mensaje, (DESTINO_IP, DESTINO_PUERTO))

        print(f"  📍 Zona: {datos['zona']:<8} | "
                f"💧 Humedad: {datos['humedad']:>5}% | "
                f"🌱 Estado: {datos['estado_suelo']:<10} | "
                f"🌡️ Temp: {datos['temperatura']}°C")

        if paquete["humedad"] < 30:
            time.sleep(5)  # Si el suelo está seco, espera más tiempo antes de enviar el siguiente dato
        else:
            time.sleep(1)

except KeyboardInterrupt:
    print()
    print("⏹️ Simulación detenida por el usuario.")
    sock.close()
except Exception as e:
    print(f"\n❌ Error durante transmisión: {e}")
    sock.close()
    sys.exit(1)