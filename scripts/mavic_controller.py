"""
mavic_controller.py — Controlador autónomo adaptado para DJI Mavic 2 PRO
Proyecto: Sistema Inteligente de Control Autónomo para Drones de Riego
Universidad Popular del Cesar
"""

from controller import Supervisor   # Requiere que en Webots actives 'supervisor TRUE' en el robot
import socket                      
import json                        
import math                        
import time                        
import random                      # Para la dispersion horizontal de las gotas de agua

# ── 1. CONFIGURACIÓN DE RED ──────────────────────────────────────────────────
UDP_IP   = "0.0.0.0"
UDP_PORT = 5006

BRIDGE_HOST = "127.0.0.1"
BRIDGE_TELEMETRY_PORT = 5005
TELEMETRY_INTERVAL_S = 1.0   

# ── 2. PARÁMETROS DE VUELO (Adaptados al Mavic) ────────────────────────────────
ALTURA_OBJETIVO = 2.0    
ALTURA_SUELO    = 0.12   # El Mavic es más alto que el Crazyflie; 12cm es ideal para detectar suelo

TOLERANCIA_XY  = 0.20    # Tolerancia horizontal aumentada por inercias del Mavic
TOLERANCIA_Z   = 0.08    

TIEMPO_RIEGO_S = 20.0

COORDENADAS_ZONAS = {
    "norte":  [ 6.0, 2.9],
    "centro": [ 1.7, 2.9],
    "sur":    [-2.5, 2.9],
}

BASE_XY = [1.65, 6.32]

# Distancia maxima permitida desde la base antes de forzar un aterrizaje de
# emergencia. Las zonas mas lejanas estan a ~5.5m de la base, asi que 15m da
# margen de sobra para navegar sin arriesgarse a perder el dron fuera del mapa.
RADIO_SEGURO_M = 15.0

# ── 3. GANANCIAS PID (Sintonizadas para DJI Mavic 2 PRO) ──────────────────────

K_ROLL_P = 6.0
K_PITCH_P = 5.0
K_ROLL_D = 1.0
K_PITCH_D = 1.0
KP_Z = 2.8
KD_Z = 1.2
THRUST_BASE = 68.5
ALTITUDE_OFFSET = 0.6
KP_POS = 0.18
KD_POS = 0.45

# ── 4. LÓGICA DIFUSA ─────────────────────────────────────────────────────────
UMBRAL_ACTIVACION = 0.35  

def mu_dry(h):
    if h <= 30: return 1.0
    if h >= 50: return 0.0
    return (50 - h) / 20.0

def mu_very_dry(h):
    if h <= 20: return 1.0
    if h >= 35: return 0.0
    return (35 - h) / 15.0

def requiere_riego(humedad: float) -> bool:
    return (mu_dry(humedad) + mu_very_dry(humedad)) > UMBRAL_ACTIVACION

# ── 6. FUNCIONES DE CONTROL PID ──────────────────────────────────────────────
def constrain(value, min_val, max_val):
    return max(min_val, min(max_val, value))

def apagar_motores():
    for m in motores:
        m.setVelocity(0.0)

# ── 7. INICIALIZACIÓN DE WEBOTS ──────────────────────────────────────────────
robot    = Supervisor()
timestep = int(robot.getBasicTimeStep())   
dt_step  = timestep / 1000.0              

# Motores específicos del Mavic 2 PRO
motores = []
motor_names = [
    "front left propeller",   # Índice 0 (FL)
    "front right propeller",  # Índice 1 (FR)
    "rear left propeller",    # Índice 2 (RL)
    "rear right propeller",   # Índice 3 (RR)
]

for name in motor_names:
    m = robot.getDevice(name)
    if m is None:
        raise RuntimeError(f"No se encontró el motor '{name}'.")
    m.setPosition(float("inf"))   
    m.setVelocity(0.0)             
    motores.append(m)

# Inicializar sensores con nombres por defecto en minúsculas (asegúrate de renombrarlos en Webots)
imu = robot.getDevice("inertial unit")
if imu is not None:
    imu.enable(timestep)
else:
    raise RuntimeError("No se pudo iniciar el dispositivo 'inertial unit'. Revisa el árbol de Webots.")

gps = robot.getDevice("gps")
if gps is not None:
    gps.enable(timestep)
else:
    raise RuntimeError("No se pudo iniciar el dispositivo 'gps'. Revisa el árbol de Webots.")

gyro = robot.getDevice("gyro")
if gyro is not None:
    gyro.enable(timestep)
else:
    print("WARNING: No se encontró un gyro. El yaw rate usará 0.0.")

# Sockets de Red
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telemetry_sock.setblocking(False)
last_telemetry_sent = 0.0

# ── 7bis. SISTEMA VISUAL DE GOTAS DE AGUA (efecto de riego) ──────────────────
# 10 esferas DEF'd en el .wbt (GOTA_0 .. GOTA_9), sin fisica, que este
# Supervisor mueve directamente por su campo "translation" para simular un
# chorro de gotas cayendo en cascada mientras el dron esta REGANDO.
#
# Simplificacion de coordenadas: en este mundo, gps_vals[2] (lo que el resto
# del controlador ya llama "actual_altitude") es directamente la coordenada Z
# global del dron, y el suelo esta en Z ~ 0 (ver traslacion inicial del
# Mavic2Pro en el .wbt, -0.084). Por eso una gota que nace en Z=altura y cae
# "altura" metros llega justo al suelo bajo el dron - no hace falta conocer
# la altura real del terreno en cada punto.
N_GOTAS = 10
GOTA_G = 9.8                  # "gravedad" visual de la caida (m/s^2)
GOTA_JITTER_XY = 0.18         # dispersion horizontal aleatoria al nacer (m)
GOTA_PARK_Z = -50.0           # posicion cuando no se esta regando (fuera de vista)

gota_fields = []
for _i in range(N_GOTAS):
    _nodo_gota = robot.getFromDef(f"GOTA_{_i}")
    if _nodo_gota is None:
        print(f"  ADVERTENCIA: no se encontro el nodo DEF GOTA_{_i} en el .wbt. "
              f"Esa gota no se movera (revisa el mundo).")
        gota_fields.append(None)
    else:
        gota_fields.append(_nodo_gota.getField("translation"))

gota_t = [0.0] * N_GOTAS              # tiempo transcurrido desde que "nacio" cada gota
gota_origen = [[0.0, 0.0, 0.0] for _ in range(N_GOTAS)]   # punto (x,y,z) de nacimiento
gotas_activas = False                  # evita reaparcar/reiniciar en cada paso sin regar


def _nacer_gota(indice, x, y, z):
    """(Re)inicia una gota en la posicion del dron, con un pequeño offset
    horizontal aleatorio para que el chorro se vea como varias gotas y no
    una sola linea perfecta."""
    gota_t[indice] = 0.0
    gota_origen[indice] = [
        x + random.uniform(-GOTA_JITTER_XY, GOTA_JITTER_XY),
        y + random.uniform(-GOTA_JITTER_XY, GOTA_JITTER_XY),
        z,
    ]


def actualizar_gotas(dt, regando, x_global, y_global, altura):
    """Anima las gotas de agua. Se llama en cada paso de simulacion.

    - Si no se esta regando (o la altura es demasiado baja para que se vea
      bien la caida): aparca las gotas fuera de vista UNA sola vez.
    - Si se esta regando: en el primer paso escalona las N gotas en el
      tiempo (para que el chorro se vea continuo desde el instante 0, no
      como si todas nacieran juntas) y luego las hace caer en paralelo,
      reciclando cada una en cuanto "toca el suelo" bajo el dron.
    """
    global gotas_activas

    if not regando or altura <= 0.05:
        if gotas_activas:
            for campo in gota_fields:
                if campo is not None:
                    campo.setSFVec3f([0.0, 0.0, GOTA_PARK_Z])
            gotas_activas = False
        return

    if not gotas_activas:
        tiempo_caida_total = math.sqrt(2.0 * max(altura, 0.05) / GOTA_G)
        for i in range(N_GOTAS):
            _nacer_gota(i, x_global, y_global, altura)
            # Escalonar el "reloj" inicial de cada gota para que, desde el
            # primer instante de riego, se vean gotas en distintas alturas
            # de caida (cascada), no todas naciendo en el mismo punto.
            gota_t[i] = (i / N_GOTAS) * tiempo_caida_total
        gotas_activas = True

    for i, campo in enumerate(gota_fields):
        gota_t[i] += dt
        ox, oy, oz = gota_origen[i]
        caida = 0.5 * GOTA_G * (gota_t[i] ** 2)

        if caida >= oz:
            # Esta gota ya "toco el suelo" (Z <= 0 aprox bajo el dron) →
            # renace desde la posicion actual del dron para mantener el
            # chorro continuo mientras se siga regando.
            _nacer_gota(i, x_global, y_global, altura)
            ox, oy, oz = gota_origen[i]
            caida = 0.0

        if campo is not None:
            campo.setSFVec3f([ox, oy, oz - caida])



# ── 8. ESPERA DE INICIALIZACIÓN ──────────────────────────────────────────────
print("=" * 60)
print("  CONTROLADOR MAVIC — SISTEMA DE RIEGO AUTÓNOMO")
print("  Universidad Popular del Cesar")
print("  Esperando 2 segundos de inicialización...")
print("=" * 60)

while robot.step(timestep) != -1:
    if robot.getTime() > 2.0:
        break   

# CORREGIDO: antes se forzaba un yaw absoluto hardcodeado (-98 grados),
# calibrado para otra sesion/mundo de Webots. Ahora se captura el yaw real
# con el que este robot arranco en ESTE mundo, para que "mantener la
# orientacion inicial" sea cierto sin importar en que .wbt se use.
YAW_INICIAL = imu.getRollPitchYaw()[2]

print("  Estado inicial: IDLE — Esperando datos de sensores...")

# ── 9. DEFINICIÓN DE ESTADOS ─────────────────────────────────────────────────
IDLE      = "IDLE"       
ASCENSO   = "ASCENSO"    
NAVEGANDO = "NAVEGANDO"  
REGANDO   = "REGANDO"    
RETORNO   = "RETORNO"    
DESCENSO  = "DESCENSO"   

estado         = IDLE              
objetivo_xy    = [0.0, 0.0]       
objetivo_zona  = None               
timer_riego    = 0.0               
height_desired = ALTURA_OBJETIVO   

# Integradores del control de posicion (X/Y). Se resetean cada vez que se fija
# un objetivo nuevo, para evitar windup entre misiones distintas.
KI_POS = 0.05
integral_x = 0.0
integral_y = 0.0
INTEGRAL_MAX = 1.5

MODO_AUTO   = "auto"
MODO_MANUAL = "manual"
modo        = MODO_AUTO

cola_zonas     = []                              
ultima_humedad = {z: None for z in COORDENADAS_ZONAS}  

# Distancias de referencia para calcular progreso real (0.0-1.0) de la FASE
# actual de vuelo. Se fijan al ENTRAR a NAVEGANDO/RETORNO y se comparan contra
# la distancia restante en cada paso. None mientras no aplique a la fase actual.

distancia_inicial_navegando = None
distancia_inicial_retorno = None

nivel_agua_estimado = 100.0

ESTADO_A_FRONTEND = {
    IDLE: "idle",
    ASCENSO: "ascenso",
    NAVEGANDO: "navegando",
    REGANDO: "regando",
    RETORNO: "retorno",
    DESCENSO: "descenso",
}

_ANCLAS_X_PCT = sorted(
    [
        (COORDENADAS_ZONAS["sur"][0], 80.0),
        (COORDENADAS_ZONAS["centro"][0], 50.0),
        (COORDENADAS_ZONAS["norte"][0], 20.0),
    ],
    key=lambda par: par[0],
)

def proyectar_a_porcentaje(x_m: float, y_m: float):
    if abs(x_m - BASE_XY[0]) < 0.2 and abs(y_m - BASE_XY[1]) < 0.5:
        return {"x": 15.0, "y": 50.0, "z": 0.0}
    
    for (x0, y0), (x1, y1) in zip(_ANCLAS_X_PCT, _ANCLAS_X_PCT[1:]):
        if x0 <= x_m <= x1:
            t = 0.0 if x1 == x0 else (x_m - x0) / (x1 - x0)
            return {"x": 50.0, "y": y0 + t * (y1 - y0), "z": 0.0}

    if x_m < _ANCLAS_X_PCT[0][0]:
        (x0, y0), (x1, y1) = _ANCLAS_X_PCT[0], _ANCLAS_X_PCT[1]
    else:
        (x0, y0), (x1, y1) = _ANCLAS_X_PCT[-2], _ANCLAS_X_PCT[-1]
    t = (x_m - x0) / (x1 - x0)
    y_pct = max(0.0, min(100.0, y0 + t * (y1 - y0)))
    return {"x": 50.0, "y": y_pct, "z": 0.0}

def enviar_telemetria(x_global, y_global, actual_altitude, speed_mps):
    global nivel_agua_estimado
    bateria_reportada = 100.0
    if estado == REGANDO:
        nivel_agua_estimado = max(0.0, nivel_agua_estimado - 0.5)

    target_pct = proyectar_a_porcentaje(*objetivo_xy) if objetivo_zona else None

    paquete = {
        "type": "drone_telemetry",
        "flightStatus": ESTADO_A_FRONTEND.get(estado, "idle"),
        "battery": bateria_reportada,
        "waterLevel": round(nivel_agua_estimado, 1),
        "speed": round(speed_mps, 3),
        "targetZone": objetivo_zona,
        "position": proyectar_a_porcentaje(x_global, y_global),
        "altitude": round(actual_altitude, 2),
        "modo": modo,
        "missionProgress": round(calcular_progreso_mision(x_global, y_global, actual_altitude), 3),
    }
    if target_pct is not None:
        paquete["targetPosition"] = target_pct

    try:
        telemetry_sock.sendto(json.dumps(paquete).encode("utf-8"), (BRIDGE_HOST, BRIDGE_TELEMETRY_PORT))
    except Exception as exc:
        print(f"  No se pudo enviar telemetria al bridge: {exc}")

def calcular_progreso_mision(x_actual: float, y_actual: float, altura_actual: float) -> float:
    """Progreso (0.0-1.0) de la FASE actual del vuelo (no de la mision
    completa, ya que esta puede visitar varias zonas en cola con
    avanzar_a_siguiente_zona_o_retorno). Usado por MissionControl.tsx para
    la barra de progreso real en vez de una animacion CSS fija.

    NOTA: en ASCENSO/DESCENSO se usa ALTURA_OBJETIVO como referencia, lo cual
    es una aproximacion razonable salvo en el caso borde de un emergency_stop
    a mitad de ASCENSO (donde el descenso empieza desde una altura menor a
    ALTURA_OBJETIVO); no afecta la logica de vuelo, solo el numero mostrado.
    """
    if estado == IDLE:
        return 0.0

    if estado == ASCENSO:
        if ALTURA_OBJETIVO <= 0:
            return 1.0
        return max(0.0, min(1.0, altura_actual / ALTURA_OBJETIVO))

    if estado == NAVEGANDO:
        if not distancia_inicial_navegando:
            return 0.0
        error_x = objetivo_xy[0] - x_actual
        error_y = objetivo_xy[1] - y_actual
        distancia_restante = math.sqrt(error_x**2 + error_y**2)
        return max(0.0, min(1.0, 1.0 - (distancia_restante / distancia_inicial_navegando)))

    if estado == REGANDO:
        if TIEMPO_RIEGO_S <= 0:
            return 1.0
        return max(0.0, min(1.0, timer_riego / TIEMPO_RIEGO_S))

    if estado == RETORNO:
        if not distancia_inicial_retorno:
            return 0.0
        error_x = objetivo_xy[0] - x_actual
        error_y = objetivo_xy[1] - y_actual
        distancia_restante = math.sqrt(error_x**2 + error_y**2)
        return max(0.0, min(1.0, 1.0 - (distancia_restante / distancia_inicial_retorno)))

    if estado == DESCENSO:
        if ALTURA_OBJETIVO <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - (height_desired / ALTURA_OBJETIVO)))

    return 0.0

def avanzar_a_siguiente_zona_o_retorno(motivo: str, x_actual: float, y_actual: float):
    global objetivo_zona, objetivo_xy, estado, timer_riego, cola_zonas
    global distancia_inicial_navegando, distancia_inicial_retorno

    if cola_zonas:
        objetivo_zona = cola_zonas.pop(0)
        objetivo_xy = COORDENADAS_ZONAS.get(objetivo_zona, [0.0, 0.0])
        timer_riego = 0.0
        estado = NAVEGANDO
        error_x0 = objetivo_xy[0] - x_actual
        error_y0 = objetivo_xy[1] - y_actual
        distancia_inicial_navegando = math.sqrt(error_x0**2 + error_y0**2) or 0.001
        print(f"  {motivo} Zonas pendientes en cola: siguiente → {objetivo_zona.upper()} (quedan {len(cola_zonas)}).")
    else:
        if modo == MODO_AUTO:
            zonas_secas_nuevas = [
                z for z, h in ultima_humedad.items()
                if h is not None and requiere_riego(h)
            ]
            
            if zonas_secas_nuevas:
                objetivo_zona = zonas_secas_nuevas[0]
                objetivo_xy = COORDENADAS_ZONAS.get(objetivo_zona, [0.0, 0.0])
                cola_zonas = zonas_secas_nuevas[1:]  
                timer_riego = 0.0
                estado = NAVEGANDO
                error_x0 = objetivo_xy[0] - x_actual
                error_y0 = objetivo_xy[1] - y_actual
                distancia_inicial_navegando = math.sqrt(error_x0**2 + error_y0**2) or 0.001
                print(f"  {motivo} Nuevas zonas secas detectadas: {objetivo_zona.upper()}")
                return
        
        objetivo_xy = BASE_XY.copy()
        objetivo_zona = None
        estado = RETORNO
        error_x0 = objetivo_xy[0] - x_actual
        error_y0 = objetivo_xy[1] - y_actual
        distancia_inicial_retorno = math.sqrt(error_x0**2 + error_y0**2) or 0.001
        print(f"  {motivo} No quedan zonas pendientes. Iniciando RETORNO.")

# Configurar valores para cálculo inicial de velocidad
past_x_global = gps.getValues()[0]
past_y_global = gps.getValues()[1]
past_altitude = gps.getValues()[2]
past_time     = robot.getTime()

# ── 10. BUCLE PRINCIPAL DE CONTROL ───────────────────────────────────────────
while robot.step(timestep) != -1:

    current_time = robot.getTime()
    dt = current_time - past_time
    if dt <= 0:
        dt = dt_step   

    # ── A. RECIBIR DATOS UDP ─────────────────────────────────────────────────
    try:
        data, _ = sock.recvfrom(4096)
        datos   = json.loads(data.decode("utf-8"))
        tipo    = datos.get("type")

        if tipo == "start_mission":
            zona = datos.get("target_zone", "sur")
            if estado == IDLE:
                objetivo_zona  = zona
                objetivo_xy    = COORDENADAS_ZONAS.get(zona, [0.0, 0.0])
                cola_zonas     = [
                    z for z, h in ultima_humedad.items()
                    if z != zona and h is not None and requiere_riego(h)
                ]
                height_desired = ALTURA_OBJETIVO
                estado         = ASCENSO
                print(f"  [PWA] start_mission → zona {zona.upper()}. Iniciando ASCENSO.")

        elif tipo == "stop_mission":
            if estado in (ASCENSO, NAVEGANDO, REGANDO):
                print("  [PWA] stop_mission → iniciando RETORNO.")
                cola_zonas  = []
                objetivo_xy = BASE_XY.copy()
                objetivo_zona = None
                estado      = RETORNO
                error_x0 = objetivo_xy[0] - past_x_global
                error_y0 = objetivo_xy[1] - past_y_global
                distancia_inicial_retorno = math.sqrt(error_x0**2 + error_y0**2) or 0.001

        elif tipo == "emergency_stop":
            if estado != IDLE:
                print("  [PWA] emergency_stop → DESCENSO inmediato.")
                cola_zonas = []
                estado = DESCENSO

        elif tipo == "set_mode":
            nuevo_modo = datos.get("mode") or datos.get("modo")
            if nuevo_modo in (MODO_AUTO, MODO_MANUAL) and nuevo_modo != modo:
                modo = nuevo_modo
                print(f"  [PWA] Modo cambiado a {modo.upper()}")

        elif "zona" in datos and "humedad" in datos:
            humedad = float(datos["humedad"])
            zona    = datos.get("zona", "centro")
            ultima_humedad[zona] = humedad

            if estado == IDLE:
                print(f"  Zona {zona.upper()}: {humedad:.1f}% | IDLE, modo {modo.upper()}")

            if estado == IDLE:
                if modo == MODO_AUTO and requiere_riego(humedad):
                    objetivo_zona  = zona
                    objetivo_xy    = COORDENADAS_ZONAS.get(zona, [0.0, 0.0])
                    cola_zonas     = [
                        z for z, h in ultima_humedad.items()
                        if z != zona and h is not None and requiere_riego(h)
                    ]
                    height_desired = ALTURA_OBJETIVO
                    integral_x     = 0.0
                    integral_y     = 0.0
                    estado         = ASCENSO
                    print(f"  [AUTO] Riego requerido en {zona.upper()}. Iniciando ASCENSO.")

            elif estado == REGANDO:
                if zona == objetivo_zona and not requiere_riego(humedad):
                    avanzar_a_siguiente_zona_o_retorno(
                        f"Zona {zona.upper()} ya no requiere riego.", past_x_global, past_y_global
                    )

    except BlockingIOError:
        pass
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"  Paquete UDP malformado: {e}")

    # ── B. LEER SENSORES ─────────────────────────────────────────────────────
    rpy = imu.getRollPitchYaw()
    actual_roll      = rpy[0]   
    actual_pitch     = rpy[1]   
    gyro_vals        = gyro.getValues() if gyro is not None else [0.0, 0.0, 0.0]
    actual_roll_rate  = gyro_vals[0]
    actual_pitch_rate = gyro_vals[1]
    actual_yaw_rate   = gyro_vals[2]

    gps_vals        = gps.getValues()
    
    x_global        = gps_vals[0]   
    y_global        = gps_vals[1]   
    actual_altitude = gps_vals[2]
    
    vertical_speed = (actual_altitude - past_altitude) / dt

    # ── SEGURIDAD: si el dron se aleja demasiado de la base, aterrizar ya ────
    # Esto no arregla la causa del desvio, pero evita perder el dron fuera
    # del mapa mientras se diagnostica con los logs de abajo.
    distancia_base = math.hypot(x_global - BASE_XY[0], y_global - BASE_XY[1])
    if distancia_base > RADIO_SEGURO_M and estado not in (IDLE, DESCENSO):
        print(f"  [SEGURIDAD] Distancia a base = {distancia_base:.1f}m > "
              f"{RADIO_SEGURO_M}m. Forzando DESCENSO de emergencia.")
        cola_zonas = []
        estado = DESCENSO

    actual_yaw = rpy[2]
    
    # Mantener siempre la orientación inicial (capturada al arrancar, no un
    # numero fijo)
    desired_yaw = YAW_INICIAL
    
    yaw_error = desired_yaw - actual_yaw
    
    while yaw_error > math.pi:
        yaw_error -= 2 * math.pi
    
    while yaw_error < -math.pi:
        yaw_error += 2 * math.pi
    
    K_YAW_D = 0.5
    desired_yaw_r = constrain(2.0 * yaw_error - K_YAW_D * actual_yaw_rate, -0.5, 0.5)
    
    vx_global  = (x_global - past_x_global) / dt   
    vy_global  = (y_global - past_y_global) / dt   
    cosyaw = math.cos(actual_yaw)
    sinyaw = math.sin(actual_yaw) 

    # ── EFECTO VISUAL: gotas de agua cayendo mientras se riega ───────────────
    actualizar_gotas(dt, estado == REGANDO, x_global, y_global, actual_altitude)

    # ── C. MÁQUINA DE ESTADOS ────────────────────────────────────────────────
    if estado == IDLE:
        apagar_motores()
    else:
        desired_vx    = 0.0
        desired_vy    = 0.0

        if estado == ASCENSO:
            error_z = height_desired - actual_altitude
            if abs(error_z) < TOLERANCIA_Z:
                print(f"  Altura {actual_altitude:.2f}m alcanzada. Transitando a NAVEGANDO")
                error_x0 = objetivo_xy[0] - x_global
                error_y0 = objetivo_xy[1] - y_global
                distancia_inicial_navegando = math.sqrt(error_x0**2 + error_y0**2) or 0.001
                estado = NAVEGANDO   # Altura lista → empezar a moverse horizontalmente
            else:
                desired_vx = 0.0
                desired_vy = 0.0
                desired_yaw_r = 0.0
                height_desired = ALTURA_OBJETIVO
                pass

        elif estado == NAVEGANDO:
            error_x = objetivo_xy[0] - x_global
            error_y = objetivo_xy[1] - y_global

            integral_x = constrain(integral_x + error_x * dt, -INTEGRAL_MAX, INTEGRAL_MAX)
            integral_y = constrain(integral_y + error_y * dt, -INTEGRAL_MAX, INTEGRAL_MAX)

            # Modificado el tope de velocidad horizontal para el peso del Mavic
            distancia = math.sqrt(error_x**2 + error_y**2)

            velocidad_max = min(0.35, distancia * 0.25)
            
            desired_vx_global = constrain(
                KP_POS * error_x + KI_POS * integral_x - KD_POS * vx_global,
                -velocidad_max,
                velocidad_max
            )
            
            desired_vy_global = constrain(
                KP_POS * error_y + KI_POS * integral_y - KD_POS * vy_global,
                -velocidad_max,
                velocidad_max
            )

            # Transformar el objetivo de velocidad global a velocidades en el eje del dron
            desired_vx = desired_vx_global * cosyaw + desired_vy_global * sinyaw
            desired_vy = -desired_vx_global * sinyaw + desired_vy_global * cosyaw

            distancia_xy = math.sqrt(error_x**2 + error_y**2)

            if distancia_xy < TOLERANCIA_XY:
                print(f"  Zona alcanzada en ({x_global:.2f}, {y_global:.2f}). Iniciando RIEGO...")
                timer_riego = 0.0
                estado      = REGANDO   

        elif estado == REGANDO:
            error_x    = objetivo_xy[0] - x_global
            error_y    = objetivo_xy[1] - y_global
            
            desired_vx_global = constrain(
                KP_POS * error_x - KD_POS * vx_global,
                -0.08,
                0.08
            )
            
            desired_vy_global = constrain(
                KP_POS * error_y - KD_POS * vy_global,
                -0.08,
                0.08
            )

            # Transformación a ejes del dron para mantener el hover estable
            desired_vx = desired_vx_global * cosyaw + desired_vy_global * sinyaw
            desired_vy = -desired_vx_global * sinyaw + desired_vy_global * cosyaw

            timer_riego += dt
            if timer_riego >= TIEMPO_RIEGO_S:
                avanzar_a_siguiente_zona_o_retorno(
                    f"Riego completado ({TIEMPO_RIEGO_S}s) en {objetivo_zona.upper()}.", x_global, y_global
                )

        elif estado == RETORNO:
            error_x    = objetivo_xy[0] - x_global
            error_y    = objetivo_xy[1] - y_global
            
            integral_x = constrain(integral_x + error_x * dt, -INTEGRAL_MAX, INTEGRAL_MAX)
            integral_y = constrain(integral_y + error_y * dt, -INTEGRAL_MAX, INTEGRAL_MAX)

            distancia = math.sqrt(error_x**2 + error_y**2)

            velocidad_max = min(0.35, distancia * 0.25)
            
            desired_vx_global = constrain(
                KP_POS * error_x + KI_POS * integral_x - KD_POS * vx_global,
                -velocidad_max,
                velocidad_max
            )
            
            desired_vy_global = constrain(
                KP_POS * error_y + KI_POS * integral_y - KD_POS * vy_global,
                -velocidad_max,
                velocidad_max
            )

            # Transformar el objetivo de velocidad global a los ejes del dron
            desired_vx = desired_vx_global * cosyaw + desired_vy_global * sinyaw
            desired_vy = -desired_vx_global * sinyaw + desired_vy_global * cosyaw

            distancia_xy = math.sqrt(error_x**2 + error_y**2)
            velocidad_actual = math.hypot(vx_global, vy_global)
            # CORREGIDO: antes solo se exigia estar cerca en XY (distancia_xy
            # < TOLERANCIA_XY), sin importar que tan rapido se siguiera
            # moviendo el dron en ese instante. Eso permitia soltar el
            # control de posicion (pasar a DESCENSO) con velocidad residual,
            # que luego se traducia en deriva durante el descenso. Ahora
            # tambien se exige que la velocidad horizontal ya sea baja.
            if distancia_xy < TOLERANCIA_XY and velocidad_actual < 0.10:
                print(f"  Base alcanzada (v={velocidad_actual:.2f}m/s). Iniciando DESCENSO")
                estado = DESCENSO   

        elif estado == DESCENSO:
            height_desired -= 0.15 * dt
            height_desired = max(0.0, height_desired)

            # Mantiene el mismo control de posicion P+I+D contra BASE_XY que
            # usa RETORNO durante todo el descenso, para no perder el
            # station-keeping mientras baja.
            error_x = BASE_XY[0] - x_global
            error_y = BASE_XY[1] - y_global

            integral_x = constrain(integral_x + error_x * dt, -INTEGRAL_MAX, INTEGRAL_MAX)
            integral_y = constrain(integral_y + error_y * dt, -INTEGRAL_MAX, INTEGRAL_MAX)

            desired_vx_global = constrain(
                KP_POS * error_x + KI_POS * integral_x - KD_POS * vx_global,
                -0.15, 0.15
            )
            desired_vy_global = constrain(
                KP_POS * error_y + KI_POS * integral_y - KD_POS * vy_global,
                -0.15, 0.15
            )
            desired_vx = desired_vx_global * cosyaw + desired_vy_global * sinyaw
            desired_vy = -desired_vx_global * sinyaw + desired_vy_global * cosyaw

            if actual_altitude <= ALTURA_SUELO + 0.02:
                print("  Dron aterrizado. Volviendo a IDLE")
                apagar_motores()
                estado = IDLE
                objetivo_zona = None
                past_time     = current_time
                past_x_global = x_global
                past_y_global = y_global
                past_altitude = actual_altitude
                continue   
             

        # ── PIPELINE PID COMPLETO ─────────────────────────────────────────────
        # CORREGIDO: el termino de posicion (roll_disturbance/pitch_disturbance)
        # era ~250 veces mas chico que K_ROLL_P/K_PITCH_P, asi que el angulo de
        # inclinacion real que se lograba era de apenas ~0.1-0.3 grados -
        # invisible frente al sesgo natural del modelo. Por eso el dron
        # practicamente ignoraba el objetivo sin importar el signo que
        # probaramos. Ahora se calcula un ANGULO OBJETIVO real (como hace
        # crazyflie_controller.py con pitch_desired/roll_desired) y el lazo de
        # actitud persigue ESE angulo, no cero.
        MAX_TILT = 0.25  # rad (~14°), inclinacion maxima seguridad para el Mavic
        K_VEL_TO_TILT = 0.4  # rad por (m/s) de velocidad deseada, antes de recortar

        if estado == ASCENSO:
            roll_desired = 0.0
            pitch_desired = 0.0
        else:
            roll_desired = constrain(-desired_vy * K_VEL_TO_TILT, -MAX_TILT, MAX_TILT)
            pitch_desired = constrain(desired_vx * K_VEL_TO_TILT, -MAX_TILT, MAX_TILT)

        roll_error = actual_roll - roll_desired
        pitch_error = actual_pitch - pitch_desired

        yaw_disturbance = desired_yaw_r

        roll_input = (
            K_ROLL_P * constrain(roll_error, -0.5, 0.5)
            + K_ROLL_D * actual_roll_rate
        )

        pitch_input = (
            K_PITCH_P * constrain(pitch_error, -0.5, 0.5)
            + K_PITCH_D * actual_pitch_rate
        )
        
        yaw_input = yaw_disturbance
        
        vertical_error = constrain(
            height_desired - actual_altitude,
            -1.0,
            1.0
        )
        
        vertical_input = (
            ALTITUDE_OFFSET
            + KP_Z * vertical_error
            - KD_Z * vertical_speed
        )
        
        vertical_input = constrain(vertical_input, -3.0, 3.0)
        
        front_left = THRUST_BASE + vertical_input - roll_input + pitch_input - yaw_input
        front_right = THRUST_BASE + vertical_input + roll_input + pitch_input + yaw_input
        rear_left = THRUST_BASE + vertical_input - roll_input - pitch_input + yaw_input
        rear_right = THRUST_BASE + vertical_input + roll_input - pitch_input - yaw_input
        
        front_left  = max(0.0, front_left)
        front_right = max(0.0, front_right)
        rear_left   = max(0.0, rear_left)
        rear_right  = max(0.0, rear_right)
        
        front_left = constrain(front_left, 0.0, 100.0)
        front_right = constrain(front_right, 0.0, 100.0)
        rear_left = constrain(rear_left, 0.0, 100.0)
        rear_right = constrain(rear_right, 0.0, 100.0)
        
        motores[0].setVelocity(front_left)
        motores[1].setVelocity(-front_right)
        motores[2].setVelocity(-rear_left)
        motores[3].setVelocity(rear_right)
        
    # ── D. ACTUALIZAR REFERENCIAS TEMPORALES ─────────────────────────────────
    past_time     = current_time
    past_x_global = x_global
    past_y_global = y_global
    past_altitude = actual_altitude

    # ── E. TELEMETRIA REAL HACIA EL BRIDGE (~1 Hz) ───────────────────────────
    if current_time - last_telemetry_sent >= TELEMETRY_INTERVAL_S:
        speed_mps = math.sqrt(vx_global ** 2 + vy_global ** 2)
        enviar_telemetria(x_global, y_global, actual_altitude, speed_mps)
        last_telemetry_sent = current_time