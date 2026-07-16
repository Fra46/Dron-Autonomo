# Conexión UDP-WebSocket para PWA de Riego Autónomo

## Universidad Popular del Cesar - Sistema de Riego Autónomo

> Este documento describe el protocolo real implementado en el código actual.
> Ver también el paper "AgroDrone: Autonomous Precision Irrigation Platform"
> (20CCC 2026) para el diseño conceptual (Fig. 1 y Fig. 2).

## Arquitectura de Comunicación

```
┌─────────────────┐                                  ┌──────────────────┐    WebSocket (8765)    ┌──────────────┐
│  sensor_nasa.py │ ── UDP 5005 (lectura de suelo) ─► │  udp_websocket   │ ◄─────────────────────► │     PWA      │
│  sensor_mock.py │                                   │    _bridge.py    │   (snapshot agregado    │  (Frontend)  │
└─────────────────┘                                   │  (agregador con  │    + comandos de misión) └──────────────┘
                                                       │     estado)      │
┌─────────────────┐                                   │                  │
│ crazyflie_      │ ── UDP 5005 (drone_telemetry) ──► │                  │
│ controller.py   │ ◄─ UDP 5006 (lecturas + cmds) ──  └──────────────────┘
│ (Webots/Dron)   │
└─────────────────┘
```

El bridge **no es un simple forwarder**: mantiene un estado agregado (`zone_readings`,
`drone_state`) que fusiona las lecturas de humedad de suelo con la telemetría
real del dron, y retransmite un snapshot completo (`type: "telemetry_update"`)
cada vez que llega un paquete UDP nuevo de cualquiera de las dos fuentes.

## Paso 1: Iniciar el Puente UDP-WebSocket

```bash
cd scripts
pip install websockets
python udp_websocket_bridge.py
```

El puente escuchará en:
- **UDP 5005:** entrada — sensores de suelo Y telemetría del dron
- **UDP 5006 (saliente):** hacia `crazyflie_controller.py` — reenvía lecturas de suelo y comandos de misión
- **WebSocket 8765:** hacia la PWA

## Paso 2: Iniciar el Sensor de Datos (NASA SMAP es la fuente principal)

### Opción A (recomendada): Datos Reales NASA SMAP (sensor_nasa.py)
```bash
pip install earthaccess h5py numpy
python sensor_nasa.py
```
Descarga datos reales del satélite SMAP de la NASA para la región del Cesar.
Requiere credenciales en `.env` (ver README principal). Si no hay credenciales
o falla la conexión remota, cae automáticamente a un fallback simulado
compatible, sin detener el flujo de telemetría.

### Opción B: Datos Simulados (sensor_mock.py)
```bash
python sensor_mock.py
```
Simula 3 zonas (norte, centro, sur) con rangos de humedad distintos. Útil
solo para desarrollo rápido sin red/credenciales.

## Paso 3: Ejecutar la PWA

```bash
npm install
npm run dev
```
La PWA se conecta automáticamente al WebSocket en `ws://localhost:8765`.

## Paso 4: Ejecutar el Dron en Webots

```bash
# En Webots, cargar el controlador crazyflie_controller.py como controlador del robot.
# Escucha en el puerto UDP 5006 (lecturas de suelo reenviadas + comandos de misión)
# y envía su telemetría real (posición, batería estimada, estado FSM) al bridge
# por UDP en el puerto 5005.
```

## Formato de Datos

### Entrada UDP al bridge — lectura de suelo (sensor_nasa.py / sensor_mock.py → bridge, puerto 5005)

```json
{
  "zona": "norte",
  "humedad": 45,
  "estado_suelo": "seco",
  "temperatura": 32.5,
  "timestamp": "2026-07-15T10:51:46.957653"
}
```

`timestamp` lo genera el propio sensor (`datetime.now().isoformat()`), no el
bridge — así queda alineado con el paper (sección 2.2: "each telemetry packet
includes... timestamp"). El bridge solo genera su propio timestamp como
respaldo si un sensor viejo no lo envía (`procesar_lectura_suelo` en
`udp_websocket_bridge.py`).

**Valores de zona:** `norte`, `centro`, `sur`

**Valores de estado_suelo:**
- `humedo` - Humedad >= 70%
- `normal` - Humedad 50-69%
- `seco` - Humedad 30-49%
- `muy_seco` - Humedad < 30%

(Estas etiquetas son descriptivas; la decisión real de activar el riego la
toma la lógica difusa del controlador, ver más abajo — no un umbral fijo aquí.)

### Entrada UDP al bridge — telemetría del dron (crazyflie_controller.py → bridge, puerto 5005)

```json
{
  "type": "drone_telemetry",
  "flightStatus": "navegando",
  "battery": 100.0,
  "waterLevel": 96.0,
  "speed": 0.42,
  "targetZone": "sur",
  "position": {"x": 50.0, "y": 65.0, "z": 0.0},
  "targetPosition": {"x": 50.0, "y": 80.0, "z": 0.0},
  "altitude": 1.97,
  "modo": "auto"
}
```

`position`/`targetPosition` ya vienen proyectadas al espacio porcentual 0-100
que usa el mapa de la PWA (`ZONE_LAYOUT` en `MapContainer.tsx`), no en metros
de Webots — ver `proyectar_a_porcentaje()` en `crazyflie_controller.py`. Su
campo `z` siempre es `0.0` (el mapa es 2D); la altitud real en metros viaja
por separado en el campo `altitude` de nivel superior.
`battery` se reporta fija en 100% (es una simulación en Webots, no hay batería
física que consumir). `waterLevel` sí es una **estimación** por tiempo
transcurrido de riego (Webots no expone un sensor real de nivel de tanque).
`modo` refleja si el controlador está en `"auto"` (riega por su cuenta) o
`"manual"` (solo por botón — ver sección "Modo de operación" más abajo).

### Salida WebSocket del bridge → PWA (snapshot agregado)

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
    "flightStatus": "navegando",
    "battery": 100.0,
    "position": {"x": 50.0, "y": 65.0, "z": 0.0},
    "targetZone": "sur",
    "waterLevel": 96.0,
    "speed": 0.42,
    "altitude": 1.97,
    "modo": "auto"
  },
  "coordinates": {"x": 50.0, "y": 65.0, "z": 0.0},
  "targetPosition": {"x": 50.0, "y": 80.0, "z": 0.0},
  "signal": 100.0,
  "temperature": 35,
  "speed": 0.42,
  "lastReading": {
    "zona": "sur", "humedad": 25, "estado": "seco", "temperatura": 35,
    "timestamp": "2026-07-15T02:48:50.239503"
  },
  "history": ["... últimas 10 lecturas de suelo ..."]
}
```

`signal` es una heurística honesta basada en cuánto hace que llegó el último
paquete de telemetría del dron (no un valor inventado): 100% si llegó hace
≤1.5s, decae a 0% a partir de 6s sin telemetría.

## Niveles de Humedad (LV0-LV5) — solo color de interfaz

| Nivel | Rango     | Estado    | Color    | Acción           |
|-------|-----------|-----------|----------|------------------|
| LV0   | 0-25%     | Crítico   | Rojo     | Riego urgente    |
| LV1   | 25-40%    | Bajo      | Naranja  | Riego necesario  |
| LV2   | 40-55%    | Moderado  | Amarillo | Monitorear       |
| LV3   | 55-70%    | Óptimo    | Verde    | OK               |
| LV4   | 70-85%    | Alto      | Cyan     | OK               |
| LV5   | 85-100%   | Saturado  | Púrpura  | Exceso de agua   |

Esta escala es independiente de la lógica difusa de activación de riego (abajo).

## Estados del Dron (Máquina de Estados)

| Estado     | Descripción                                    |
|------------|------------------------------------------------|
| `idle`     | En tierra, motores apagados, esperando alerta  |
| `ascenso`  | Subiendo hasta altura de crucero (1.0m)        |
| `navegando`| Volando hacia la zona con humedad crítica      |
| `regando`  | Hover fijo sobre la zona, aplicando riego      |
| `retorno`  | Volviendo a la base [0, 0]                     |
| `descenso` | Bajando controladamente hasta aterrizar        |

## Coordenadas de Zonas (Webots/Virtual Planet)

```python
COORDENADAS_ZONAS = {
    "norte":  [ 6.0, 2.9],   # Sector típicamente más húmedo
    "centro": [ 1.7, 2.9],
    "sur":    [-2.5, 2.9],   # Sector típicamente más seco
}
BASE_XY = [1.65, 6.32]

ALTURA_OBJETIVO = 2.0    # Metros
TOLERANCIA_XY   = 0.15   # Metros
TIEMPO_RIEGO_S  = 20.0   # Segundos
```

Las tres zonas comparten la misma `y` real (2.9) y solo varían en `x`;
`proyectar_a_porcentaje()` en `crazyflie_controller.py` interpola linealmente
la `x` real del dron contra esas tres anclas (`sur→80%`, `centro→50%`,
`norte→20%` en el eje vertical del mapa) y recorta el resultado a `[0,100]`
para posiciones fuera de rango, como la base — así, si alguien reajusta estas
coordenadas para el mundo de Webots, el mapa de la PWA se sigue viendo
correcto sin tocar la fórmula.

## Modo de operación y misiones multi-zona

El controlador tiene 2 modos, elegibles desde el switch en `MissionControl.tsx`
(comando `set_mode`):

- **`auto`** (por defecto): en cuanto la lógica difusa detecta una zona seca
  y el dron está en `IDLE`, despega solo, sin esperar ningún botón.
- **`manual`**: el dron solo despega cuando la PWA envía `start_mission`.

En cualquiera de los 2 modos, si al iniciar una misión *otras* zonas ya
conocidas también están secas, se encolan (`cola_zonas`) y el dron las visita
todas antes de volver a la base — en vez de aterrizar e ignorarlas hasta que
llegue la siguiente lectura de esa zona y tenga que volver a despegar.

## Lógica Difusa del Controlador (igual que el paper, ecuaciones 1-3)

```python
UMBRAL_ACTIVACION = 0.65  # theta, calibrado empiricamente (paper, Tabla 2)

def mu_dry(h):        # ecuacion 1: 1 si h<=30, (50-h)/20 si 30<h<50, 0 si h>=50
    ...

def mu_very_dry(h):    # ecuacion 2: 1 si h<=20, (35-h)/15 si 20<h<35, 0 si h>=35
    ...

def requiere_riego(humedad):
    return (mu_dry(humedad) + mu_very_dry(humedad)) > UMBRAL_ACTIVACION
```

## Comandos desde la PWA

La PWA envía comandos al bridge por WebSocket, que los reenvía por UDP al
controlador en el puerto 5006 (excepto `request_status`, que el bridge
responde directamente sin tocar el controlador):

```json
{"type": "start_mission", "target_zone": "sur"}
{"type": "stop_mission"}
{"type": "emergency_stop"}
{"type": "request_status", "client_ts": 1784112707551}
{"type": "set_mode", "modo": "manual"}
```

Los cinco están expuestos en la UI de `MissionControl.tsx` ("Iniciar misión",
"Detener Misión", "Parada de emergencia", "Sincronizar estado", y el switch
"Modo automático").

## Latencia en vivo en la PWA (panel "Latencia PWA↔Bridge")

Además del script de consola (`measure_bridge_latency.py`), la propia PWA
muestra su latencia real ida-y-vuelta en `TelemetryBar.tsx`, sin depender de
relojes sincronizados entre máquinas:

1. La PWA envía `request_status` con `client_ts: Date.now()` (su propio reloj
   de navegador) — automáticamente cada 3s mientras esté conectada (ver
   `use-telemetry.ts`), además de cuando el usuario presiona "Sincronizar estado".
2. El bridge responde a **ese cliente específico** (no lo transmite a todos)
   con el snapshot habitual más un campo extra `pingTs` = el mismo `client_ts`
   que recibió, sin modificarlo.
3. La PWA calcula `latencia = Date.now() - pingTs` — con su propio reloj en
   ambos extremos de la resta, así que no importa si el bridge corre en otra
   máquina de la LAN con un reloj distinto; el número es correcto de todas formas.

Esto es lo mismo que hace `measure_bridge_latency.py` (single-observer: quien
mide es el mismo proceso que envía y recibe), aplicado dentro del navegador
para que se vea en vivo durante la demo, incluso desde un teléfono.

## Componentes de la PWA

| Componente        | Función                                         |
|-------------------|-------------------------------------------------|
| `ScorePanel`      | Muestra humedad promedio y por zona (norte/centro/sur) |
| `BigScoreSummary` | Estado general: ESTRATÉGICO u OPORTUNO          |
| `MissionControl`  | Control de misión, parada de emergencia y sincronización |
| `TelemetryBar`    | Batería, señal, altitud, velocidad, temperatura en tiempo real |
| `MapContainer`    | Mapa con posición real del dron y zonas         |

## Troubleshooting

### La PWA no actualiza datos, pero el WebSocket conecta
- Confirma que el paquete recibido tiene `"type": "telemetry_update"` (o
  `"initial_state"`) — si el bridge se modifica para reenviar paquetes crudos
  sin agregarlos, la PWA los ignora silenciosamente. `src/lib/telemetry.ts`
  (`parseTelemetryMessage`) documenta el contrato exacto esperado.

### No llegan datos del sensor
- Verifica que `sensor_mock.py` o `sensor_nasa.py` esté corriendo
- Ambos deben enviar al puerto 5005 en localhost
- El puente debe mostrar "UDP recibido" o el log de `procesar_lectura_suelo` en la consola

### El dron no responde en Webots / no llega telemetría del dron
- El controlador `crazyflie_controller.py` debe escuchar en el puerto **5006**,
  no 5005 (5005 lo usa el bridge para recibir; si el controlador también
  intentara bindear 5005 en la misma máquina, fallaría con
  `Address already in use`).
- Verifica que `BRIDGE_HOST`/`BRIDGE_TELEMETRY_PORT` en el controlador
  apunten a `127.0.0.1:5005`.

## Requisitos

```bash
# Para el puente
pip install websockets

# Para sensor_nasa.py
pip install earthaccess h5py numpy

# Para la PWA (ya incluido en package.json)
npm install
npm run dev
```
