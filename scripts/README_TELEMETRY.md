# Conexion UDP-WebSocket para PWA de Riego Autonomo

## Universidad Popular del Cesar - Sistema de Riego Autonomo

## Arquitectura de Comunicacion

```
┌─────────────────┐     UDP (5005)      ┌──────────────────┐     WebSocket (8765)    ┌──────────────┐
│  sensor_mock.py │ ──────────────────► │  udp_websocket   │ ◄────────────────────► │     PWA      │
│  sensor_nasa.py │                     │    _bridge.py    │                         │  (Frontend)  │
└─────────────────┘                     └──────────────────┘                         └──────────────┘
        │                                       ▲
        │                                       │
        ▼                                       │
┌─────────────────┐                             │
│ crazyflie_      │ ◄───────────────────────────┘
│ controller.py   │   (Lee mismos datos UDP en Webots)
│ (Webots/Dron)   │
└─────────────────┘
```

## Paso 1: Iniciar el Puente UDP-WebSocket

Este script recibe los datos UDP de los sensores y los reenvía a la PWA via WebSocket:

```bash
cd scripts
pip install websockets
python udp_websocket_bridge.py
```

El puente escuchará en:
- **UDP:** Puerto 5005 (recibe datos del sensor)
- **WebSocket:** Puerto 8765 (envía a la PWA)

## Paso 2: Iniciar el Simulador de Sensores

### Opcion A: Datos Simulados (sensor_mock.py)
```bash
python sensor_mock.py
```

Simula 3 zonas (norte, centro, sur) con rangos de humedad distintos.

### Opcion B: Datos Reales NASA SMAP (sensor_nasa.py)
```bash
pip install earthaccess h5py numpy
python sensor_nasa.py
```

Descarga datos reales del satelite SMAP de la NASA para la region del Cesar.

## Paso 3: Ejecutar la PWA

La PWA se conecta automaticamente al WebSocket en `ws://localhost:8765`.

En modo desarrollo, si no hay conexion UDP, la PWA entra en **modo simulacion (SIM)** automaticamente.

## Paso 4: Ejecutar el Dron en Webots (Opcional)

```bash
# En Webots, cargar el controlador crazyflie_controller.py
# El dron escucha en el mismo puerto UDP 5005
```

## Formato de Datos del Sensor

### Entrada UDP (JSON desde sensor_mock.py / sensor_nasa.py)

```json
{
  "zona": "norte",
  "humedad": 45,
  "estado_suelo": "seco",
  "temperatura": 32.5
}
```

**Valores de zona:** `norte`, `centro`, `sur`

**Valores de estado_suelo:**
- `humedo` - Humedad >= 70%
- `normal` - Humedad 50-69%
- `seco` - Humedad 30-49%
- `muy_seco` - Humedad < 30% (activa el riego automatico)

### Salida WebSocket (JSON a la PWA)

```json
{
  "type": "telemetry_update",
  "zones": {
    "norte": {"humedad": 75, "estado": "humedo", "temperatura": 30, "nivel": "lv4"},
    "centro": {"humedad": 50, "estado": "normal", "temperatura": 32, "nivel": "lv2"},
    "sur": {"humedad": 25, "estado": "seco", "temperatura": 35, "nivel": "lv1"}
  },
  "humidityZones": {"lv0": 0, "lv1": 1, "lv2": 1, "lv3": 0, "lv4": 1, "lv5": 0},
  "averageHumidity": 50,
  "drone": {
    "flightStatus": "idle",
    "battery": 100,
    "position": {"x": 0, "y": 0, "z": 0},
    "targetZone": null,
    "waterLevel": 100
  },
  "lastReading": {
    "zona": "sur",
    "humedad": 25,
    "estado": "seco",
    "temperatura": 35
  }
}
```

## Niveles de Humedad (LV0-LV5) - Colores de Rojo a Purpura

| Nivel | Rango     | Estado    | Color    | Accion           |
|-------|-----------|-----------|----------|------------------|
| LV0   | 0-25%     | Critico   | Rojo     | Riego urgente    |
| LV1   | 25-40%    | Bajo      | Naranja  | Riego necesario  |
| LV2   | 40-55%    | Moderado  | Amarillo | Monitorear       |
| LV3   | 55-70%    | Optimo    | Verde    | OK               |
| LV4   | 70-85%    | Alto      | Cyan     | OK               |
| LV5   | 85-100%   | Saturado  | Purpura  | Exceso de agua   |

## Estados del Dron (Maquina de Estados)

| Estado     | Descripcion                                    |
|------------|------------------------------------------------|
| `idle`     | En tierra, motores apagados, esperando alerta  |
| `ascenso`  | Subiendo hasta altura de crucero (1.0m)        |
| `navegando`| Volando hacia la zona con humedad critica      |
| `regando`  | Hover fijo sobre la zona, aplicando riego      |
| `retorno`  | Volviendo a la base [0, 0]                     |
| `descenso` | Bajando controladamente hasta aterrizar        |

## Coordenadas de Zonas (Webots/Virtual Planet)

```python
COORDENADAS_ZONAS = {
    "norte":  [ 1.5,  1.5],   # Sector tipicamente mas humedo
    "centro": [ 0.0,  0.0],   # Base del dron
    "sur":    [-1.5, -1.5],   # Sector tipicamente mas seco
}

ALTURA_OBJETIVO = 1.0    # Metros
TOLERANCIA_XY   = 0.15   # Metros
TIEMPO_RIEGO_S  = 10.0   # Segundos
```

## Logica Difusa del Controlador

El dron usa logica difusa para decidir cuando activar el riego:

```python
def requiere_riego(humedad):
    # mu_muy_seco: 1.0 si humedad <= 15%, 0.0 si >= 30%
    # mu_seco: triangular con pico en 35%
    return (mu_muy_seco(humedad) + mu_seco(humedad)) > 0.5
```

## Comandos desde la PWA

La PWA puede enviar comandos al puente:

```json
{"type": "start_mission", "target_zone": "sur"}
{"type": "stop_mission"}
{"type": "emergency_stop"}
{"type": "request_status"}
```

## Componentes de la PWA

| Componente        | Funcion                                         |
|-------------------|-------------------------------------------------|
| `ScorePanel`      | Muestra humedad promedio y por zona (norte/centro/sur) |
| `BigScoreSummary` | Estado general: ESTRATEGICO o OPORTUNO          |
| `LevelButtons`    | Botones LV0-LV5 que cambian de rojo a purpura   |
| `MissionControl`  | Control de mision con seleccion de zona         |
| `TelemetryBar`    | Coordenadas, bateria, senal en tiempo real      |
| `MapContainer`    | Mapa con posicion del dron y zonas              |

## Troubleshooting

### La PWA muestra "SIM" en lugar de "UDP"
- Verifica que `udp_websocket_bridge.py` este corriendo
- Verifica que el puerto 8765 este disponible
- Revisa la consola del navegador para errores de WebSocket

### No llegan datos del sensor
- Verifica que `sensor_mock.py` o `sensor_nasa.py` este corriendo
- Ambos deben enviar al puerto 5005 en localhost
- El puente debe mostrar "UDP recibido" en la consola

### El dron no responde en Webots
- El controlador `crazyflie_controller.py` escucha en puerto 5005
- Nota: Si el puente y el controlador corren en la misma maquina, 
  ambos intentaran usar el puerto 5005. El puente tiene prioridad.
- Para desarrollo, usa solo el puente; para simulacion completa,
  modifica los puertos.

## Requisitos

```bash
# Para el puente
pip install websockets

# Para sensor_nasa.py
pip install earthaccess h5py numpy

# Para la PWA (ya incluido en package.json)
pnpm install
pnpm dev
```
