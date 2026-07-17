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

# ── 3. GANANCIAS PID (Sintonizadas para DJI Mavic 2 PRO) ──────────────────────

K_ROLL_P = 50.0
K_PITCH_P = 30.0
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

# ── 8. ESPERA DE INICIALIZACIÓN ──────────────────────────────────────────────
print("=" * 60)
print("  CONTROLADOR MAVIC — SISTEMA DE RIEGO AUTÓNOMO")
print("  Universidad Popular del Cesar")
print("  Esperando 2 segundos de inicialización...")
print("=" * 60)

while robot.step(timestep) != -1:
    if robot.getTime() > 2.0:
        break   

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

MODO_AUTO   = "auto"
MODO_MANUAL = "manual"
modo        = MODO_AUTO

cola_zonas     = []                              
ultima_humedad = {z: None for z in COORDENADAS_ZONAS}  
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
    }
    if target_pct is not None:
        paquete["targetPosition"] = target_pct

    try:
        telemetry_sock.sendto(json.dumps(paquete).encode("utf-8"), (BRIDGE_HOST, BRIDGE_TELEMETRY_PORT))
    except Exception as exc:
        print(f"  No se pudo enviar telemetria al bridge: {exc}")

def avanzar_a_siguiente_zona_o_retorno(motivo: str):
    global objetivo_zona, objetivo_xy, estado, timer_riego, cola_zonas

    if cola_zonas:
        objetivo_zona = cola_zonas.pop(0)
        objetivo_xy = COORDENADAS_ZONAS.get(objetivo_zona, [0.0, 0.0])
        timer_riego = 0.0
        estado = NAVEGANDO
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
                print(f"  {motivo} Nuevas zonas secas detectadas: {objetivo_zona.upper()}")
                return
        
        objetivo_xy = BASE_XY.copy()
        objetivo_zona = None
        estado = RETORNO
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
                    estado         = ASCENSO
                    print(f"  [AUTO] Riego requerido en {zona.upper()}. Iniciando ASCENSO.")

            elif estado == REGANDO:
                if zona == objetivo_zona and not requiere_riego(humedad):
                    avanzar_a_siguiente_zona_o_retorno(f"Zona {zona.upper()} ya no requiere riego.")

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

    actual_yaw = rpy[2]
    
    # Mantener siempre la orientación inicial
    desired_yaw = math.radians(-98.0)
    
    yaw_error = desired_yaw - actual_yaw
    
    while yaw_error > math.pi:
        yaw_error -= 2 * math.pi
    
    while yaw_error < -math.pi:
        yaw_error += 2 * math.pi
    
    desired_yaw_r = constrain(2.0 * yaw_error, -0.5, 0.5)
    
    vx_global  = (x_global - past_x_global) / dt   
    vy_global  = (y_global - past_y_global) / dt   
    cosyaw = math.cos(actual_yaw)
    sinyaw = math.sin(actual_yaw) 

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
                estado = NAVEGANDO   
            else:
                desired_vx = 0.0
                desired_vy = 0.0
                desired_yaw_r = 0.0
                height_desired = ALTURA_OBJETIVO
                pass

        elif estado == NAVEGANDO:
            error_x = objetivo_xy[0] - x_global
            error_y = objetivo_xy[1] - y_global

            # Modificado el tope de velocidad horizontal para el peso del Mavic
            distancia = math.sqrt(error_x**2 + error_y**2)

            velocidad_max = min(0.35, distancia * 0.25)
            
            desired_vx_global = constrain(
                KP_POS * error_x - KD_POS * vx_global,
                -velocidad_max,
                velocidad_max
            )
            
            desired_vy_global = constrain(
                KP_POS * error_y - KD_POS * vy_global,
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
                avanzar_a_siguiente_zona_o_retorno(f"Riego completado ({TIEMPO_RIEGO_S}s) en {objetivo_zona.upper()}.")

        elif estado == RETORNO:
            error_x    = objetivo_xy[0] - x_global
            error_y    = objetivo_xy[1] - y_global
            
            distancia = math.sqrt(error_x**2 + error_y**2)

            velocidad_max = min(0.35, distancia * 0.25)
            
            desired_vx_global = constrain(
                KP_POS * error_x - KD_POS * vx_global,
                -velocidad_max,
                velocidad_max
            )
            
            desired_vy_global = constrain(
                KP_POS * error_y - KD_POS * vy_global,
                -velocidad_max,
                velocidad_max
            )

            # Transformar el objetivo de velocidad global a los ejes del dron
            desired_vx = desired_vx_global * cosyaw + desired_vy_global * sinyaw
            desired_vy = -desired_vx_global * sinyaw + desired_vy_global * cosyaw

            distancia_xy = math.sqrt(error_x**2 + error_y**2)
            if distancia_xy < TOLERANCIA_XY:
                print(f"  Base alcanzada. Iniciando DESCENSO")
                estado = DESCENSO   

        elif estado == DESCENSO:
            height_desired -= 0.15 * dt
            height_desired = max(0.0, height_desired)
            desired_vx     = 0.0   
            desired_vy     = 0.0

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
        K_POS_TO_ATT = 0.20

        if estado == ASCENSO:
            roll_disturbance = 0.0
            pitch_disturbance = 0.0
        else:
            roll_disturbance = -desired_vy * K_POS_TO_ATT
            pitch_disturbance = desired_vx * K_POS_TO_ATT
        
        yaw_disturbance = desired_yaw_r
        
        roll_input = (
            K_ROLL_P * constrain(actual_roll, -1.0, 1.0)
            + actual_roll_rate
            + roll_disturbance
        )
        
        pitch_input = (
            K_PITCH_P * constrain(actual_pitch, -1.0, 1.0)
            + actual_pitch_rate
            + pitch_disturbance
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
        
        