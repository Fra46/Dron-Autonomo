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


DESTINO_IP     = "127.0.0.1"
DESTINO_PUERTO = 5005


print("Conexion con la nasa")
print()

auth = earthaccess.login(strategy="interactive")
print("Conexión exitosa\n")

# Busca datos del satélite SMAP 
print("Buscando datos de humedad del suelo (SMAP)")


resultados = earthaccess.search_data(
    # Usamos el satelite que se encarga de medir la humedad del suelo: SMAP
    short_name="SPL3SMP",
    # Solo archivos que cubran el área del Cesar
    bounding_box=(-74, 9, -72, 11),
    # Solo archivos en este rango de fechas
    temporal=("2024-06-01", "2024-06-03")
)

# Descarga el primer archivo encontrado para obtener los datos reales.
print(f"Archivos encontrados: {len(resultados)}")
print("Descargando datos reales\n")

archivos_locales = glob.glob("SMAP_L3_SM_P_*.h5")

if len(archivos_locales) > 0:
    print(f"  Archivos ya descargados ({len(archivos_locales)} encontrados)")
    archivos = archivos_locales
else:
    print("  Descargando datos")
    archivos = earthaccess.download(resultados, local_path=".")


print("Extraemos los valores reales de humedad del suelo para la región del Cesar\n")

# Definir límites geográficos del Cesar para filtrar los datos
LAT_MIN, LAT_MAX =  9.0, 11.0
LON_MIN, LON_MAX = -74.0, -72.0

# Aqui guardaremos los valores reales de humedad del suelo que correspondan a la región del Cesar
valores_reales = []

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
                    valores_reales.append(round(float(hum) * 100, 1))

print(f"Valores reales extraídos: {len(valores_reales)}")

# Confirmamos que se encontraron datos válidos para la región del Cesar
if len(valores_reales) == 0:
    print("\nNo se encontraron valores válidos para la región.")
    print(" Intenta cambiar las fechas en temporal=()")
    exit()

# Guardar mínimo y máximo para calcular estados relativos
humedad_minima  = min(valores_reales)
humedad_maxima  = max(valores_reales)
humedad_promedio = round(sum(valores_reales) / len(valores_reales), 1)

# Mostramos resumen de los datos reales obtenidos
print(f"  Humedad mínima real:    {humedad_minima}%")
print(f"  Humedad máxima real:    {humedad_maxima}%")
print(f"  Humedad promedio real:  {humedad_promedio}%\n")

# Divide los valores en tercios para asignarles
# una zona geográfica según su nivel de humedad.
# El tercio más húmedo → norte
# El tercio medio      → centro
# El tercio más seco   → sur
# ordenamos de menor a mayor
valores_reales.sort()

total  = len(valores_reales)
tercio = total // 3

valores_sur    = valores_reales[:tercio]
valores_centro = valores_reales[tercio:tercio * 2]
valores_norte  = valores_reales[tercio * 2:]

print(f"Total: {total}, Tercio: {tercio}")
print(f"Sur: {len(valores_sur)}")
print(f"Centro: {len(valores_centro)}")
print(f"Norte: {len(valores_norte)}")

paquetes = []

for v in valores_sur:
    paquetes.append({"zona": "sur",    "humedad": v})
for v in valores_centro:
    paquetes.append({"zona": "centro", "humedad": v})
for v in valores_norte:
    paquetes.append({"zona": "norte",  "humedad": v})

# Usamos itertools.cycle(), cuando se acaben los datos reales,
# vuelve a empezar desde el primero
ciclo_paquetes = itertools.cycle(paquetes)

print(f"  Distribución de valores por zona:")
print(f"  Sur:    {len(valores_sur)} valores | "
        f"{min(valores_sur)}% a {max(valores_sur)}%")
print(f"  Centro: {len(valores_centro)} valores | "
        f"{min(valores_centro)}% a {max(valores_centro)}%")
print(f"  Norte:  {len(valores_norte)} valores | "
        f"{min(valores_norte)}% a {max(valores_norte)}%\n")

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
    
print("  SIMULADOR DE SENSORES - DRON DE RIEGO")
print("  Datos reales del satélite NASA SMAP")
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

        print(f"  Zona: {datos['zona']:<8} | "
                f"Humedad: {datos['humedad']:>5}% | "
                f"Estado: {datos['estado_suelo']:<10} | "
                f"Temperatura: {datos['temperatura']}°C")

        if paquete["humedad"] < 30:
            time.sleep(5)  # Si el suelo está seco, espera más tiempo antes de enviar el siguiente dato
        else:
            time.sleep(1)

except KeyboardInterrupt:
    print()
    print("  Simulación detenida por el usuario.")
    sock.close()