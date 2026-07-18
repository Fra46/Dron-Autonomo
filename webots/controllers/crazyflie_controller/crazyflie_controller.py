"""
crazyflie_controller.py — Controlador autónomo con NAVEGACIÓN y MÁQUINA DE ESTADOS
Proyecto: Sistema Inteligente de Control Autónomo para Drones de Riego
Universidad Popular del Cesar

ESTADOS DEL SISTEMA:
  IDLE       → Motores apagados, dron en tierra. Espera una alerta de riego.
  ASCENSO    → Sube hasta ALTURA_OBJETIVO antes de moverse lateralmente.
  NAVEGANDO  → Vuela hacia la zona con humedad crítica.
  REGANDO    → Mantiene posición sobre la zona (hover fijo).
  RETORNO    → Vuelve a la base [0, 0] después de completar el riego.
  DESCENSO   → Baja controladamente hasta tocar el suelo.
"""

from controller import Robot   # API de Webots para controlar el robot simulado
import socket                  # Para recibir datos UDP del bridge y enviar telemetria
import json                    # Para parsear/serializar los paquetes JSON
import math                    # Para operaciones trigonométricas (cos, sin, sqrt)
import time                    # Para muestrear velocidad de envio de telemetria

# ── 1. CONFIGURACIÓN DE RED ──────────────────────────────────────────────────
# El controlador escucha en el puerto que el bridge usa para reenviar lecturas
# de suelo y comandos de mision (ver CONTROLLER_CMD_PORT en
# scripts/udp_websocket_bridge.py). NO debe coincidir con el puerto 5005 donde
# el propio bridge escucha, o ambos procesos no podrían bindear ese puerto
# al mismo tiempo en la misma máquina.
UDP_IP   = "0.0.0.0"
UDP_PORT = 5006

# Socket de salida: aquí el controlador envía su telemetría real (posición,
# batería estimada, estado de la máquina de estados) de vuelta al bridge,
# que la fusiona con las lecturas de suelo y la retransmite a la PWA.
BRIDGE_HOST = "127.0.0.1"
BRIDGE_TELEMETRY_PORT = 5005
TELEMETRY_INTERVAL_S = 1.0   # ~1 Hz, igual que el resto del pipeline (paper: "1 Hz nominal")

# ── 2. PARÁMETROS DE VUELO ───────────────────────────────────────────────────
ALTURA_OBJETIVO = 2.0    # Altura de crucero en metros (el dron vuela a esta altura)
ALTURA_SUELO    = 0.05   # Si el GPS marca menos de 5cm, se considera que aterrizó

# Márgenes de error aceptables para considerar que llegó al destino
TOLERANCIA_XY  = 0.15    # metros — tolerancia horizontal (llegar a la zona)
TOLERANCIA_Z   = 0.05    # metros — tolerancia vertical (alcanzar la altura de crucero)

# Cuántos segundos (simulados) riega el dron antes de volver a casa
TIEMPO_RIEGO_S = 20.0

# Posiciones físicas (X, Y) dentro del mundo 3D de Webots para cada zona del Cesar
# Estas coordenadas corresponden a norte, centro y sur del área monitoreada
COORDENADAS_ZONAS = {
    "norte":  [ 6.0, 2.9],
    "centro": [ 1.7, 2.9],
    "sur":    [-2.5, 2.9],
}

BASE_XY = [1.65, 6.32]

# ── 3. GANANCIAS PID ─────────────────────────────────────────────────────────
# Estas ganancias son idénticas a las del archivo crazyflie.c original de Webots.
# Cambiarlas afecta la estabilidad y velocidad de respuesta del dron.

# Controlador de actitud (orienta el dron: roll y pitch)
KP_ATT_RP  = 0.5    # Cuánto corrige el ángulo de inclinación (roll/pitch)
KD_ATT_RP  = 0.1    # Amortigua oscilaciones en la inclinación
KP_ATT_Y   = 1.0    # Cuánto corrige la rotación sobre el eje vertical (yaw)
KD_ATT_Y   = 0.5    # Amortigua oscilaciones en la rotación (no se usa actualmente)

# Controlador de velocidad horizontal (cuánto se inclina para moverse)
KP_VEL_XY  = 1.0    # Ganancia proporcional de velocidad horizontal
KD_VEL_XY  = 0.2    # Amortigua cambios bruscos de velocidad horizontal

# Controlador de altura (mantiene o cambia la altitud del dron)
KP_Z       = 5.0   # Responde agresivamente a errores de altura
KI_Z       = 0.5    # Elimina el error estático acumulado en altura
KD_Z       = 2.5    # Amortigua las oscilaciones verticales

# Empuje base en hover: valor constante que compensa la gravedad
# (viene hardcoded como "+48" en pid_controller.c del firmware original)
THRUST_BASE = 47.0

# ── 4. LÓGICA DIFUSA ─────────────────────────────────────────────────────────
# Implementa exactamente las ecuaciones (1)-(3) del paper "AgroDrone:
# Autonomous Precision Irrigation Platform" (20CCC 2026):
#   mu_dry(h)      = 1          si h <= 30
#                  = (50-h)/20  si 30 < h < 50
#                  = 0          si h >= 50
#   mu_very_dry(h) = 1          si h <= 20
#                  = (35-h)/15  si 20 < h < 35
#                  = 0          si h >= 35
#   activa riego si mu_dry(h) + mu_very_dry(h) > theta, theta = 0.65
# (theta calibrado empiricamente en el paper, seccion 2.3)
#
# AJUSTE: Se redujo theta de 0.65 a 0.35 para incluir riego en humedad media (lv2),
# permitiendo que el dron riegue preventivamente cuando la humedad está en nivel
# "medio" (~40-55%), en vez de esperar a que descienda a "bajo" (~25-40%).
# Esto evita cambios bruscos de humedad de bajo a crítico.

UMBRAL_ACTIVACION = 0.35  # Reducido para incluir humedad media (lv2)

def mu_dry(h):
    """Funcion de membresia difusa para 'suelo SECO' (ecuacion 1 del paper)."""
    if h <= 30:
        return 1.0
    if h >= 50:
        return 0.0
    return (50 - h) / 20.0

def mu_very_dry(h):
    """Funcion de membresia difusa para 'suelo MUY SECO' (ecuacion 2 del paper)."""
    if h <= 20:
        return 1.0
    if h >= 35:
        return 0.0
    return (35 - h) / 15.0

def requiere_riego(humedad: float) -> bool:
    """Decide si una zona necesita riego usando logica difusa (ecuacion 3
    del paper): activa la mision si mu_dry(h) + mu_very_dry(h) > theta.
    """
    return (mu_dry(humedad) + mu_very_dry(humedad)) > UMBRAL_ACTIVACION

# ── 5. ESTADO DEL PID ────────────────────────────────────────────────────────
# El controlador PID necesita recordar valores del paso anterior
# para calcular derivadas e integrales. Esta clase agrupa todas
# esas variables en un solo objeto, reemplazando las variables
# globales que usa el firmware C original.

class PIDState:
    """
    Almacena el estado interno de todos los controladores PID.
    Se actualiza en cada paso del bucle de control.
    """
    def __init__(self):
        self.past_altitude_error  = 0.0   # Error de altura en el paso anterior
        self.past_pitch_error     = 0.0   # Error de pitch (inclinación frontal) anterior
        self.past_roll_error      = 0.0   # Error de roll (inclinación lateral) anterior
        self.past_yaw_rate_error  = 0.0   # Error de velocidad de giro anterior
        self.past_vx_error        = 0.0   # Error de velocidad X anterior
        self.past_vy_error        = 0.0   # Error de velocidad Y anterior
        self.altitude_integrator  = 0.0   # Acumulador del término integral de altura
        self.past_x_global        = 0.0   # Posición X del paso anterior (para calcular velocidad)
        self.past_y_global        = 0.0   # Posición Y del paso anterior (para calcular velocidad)

# Instancia global del estado PID (se usa en todas las funciones de control)
pid = PIDState()

# ── 6. FUNCIONES DE CONTROL PID ──────────────────────────────────────────────

def constrain(value, min_val, max_val):
    """
    Limita un valor dentro de un rango [min_val, max_val].
    Equivalente a la macro constrain() del firmware C.
    Evita que los comandos de control salgan del rango seguro.
    """
    return max(min_val, min(max_val, value))

def pid_fixed_height_controller(actual_altitude, desired_altitude, dt):
    """
    Controlador PID de altura fija.
    Réplica de pid_fixed_height_controller() en pid_controller.c

    Calcula cuánta potencia de empuje necesitan los motores para
    mantener o alcanzar la altura deseada.

    Parámetros:
        actual_altitude  → altura actual medida por el GPS (metros)
        desired_altitude → altura objetivo (metros)
        dt               → tiempo transcurrido desde el último paso (segundos)

    Retorna:
        altitude_cmd → comando de empuje total para los 4 motores
    """
    # Error actual: diferencia entre lo deseado y lo real
    altitude_error = desired_altitude - actual_altitude

    # Término derivativo: tasa de cambio del error (evita sobrepasar la altura)
    altitude_derivative_error = (altitude_error - pid.past_altitude_error) / dt

    # Término integral: acumula el error para eliminar offset estático
    pid.altitude_integrator += altitude_error * dt

    # Comando final: P + D + I + offset base de hover
    altitude_cmd = (
        KP_Z * constrain(altitude_error, -1, 1)     # Proporcional (corrige el error)
        + KD_Z * altitude_derivative_error           # Derivativo (amortigua)
        + KI_Z * pid.altitude_integrator             # Integral (elimina offset)
        + THRUST_BASE                                # Empuje base para contrarrestar gravedad
    )
    
    altitude_cmd = constrain(altitude_cmd, 35.0, 60.0)

    # Guardar el error actual para el siguiente paso
    pid.past_altitude_error = altitude_error
    return altitude_cmd

def pid_attitude_controller(actual_roll, actual_pitch, actual_yaw_rate,
                             desired_roll, desired_pitch, desired_yaw_rate, dt):
    """
    Controlador PID de actitud (orientación del dron).
    Réplica de pid_attitude_controller() en pid_controller.c

    Corrige la inclinación (roll/pitch) y la rotación (yaw) del dron
    para que apunte y se incline en la dirección correcta.

    Parámetros:
        actual_roll/pitch/yaw_rate  → valores reales del IMU y giróscopo
        desired_roll/pitch/yaw_rate → valores objetivo calculados por el controlador de velocidad
        dt                          → tiempo transcurrido (segundos)

    Retorna:
        roll_cmd, pitch_cmd, yaw_cmd → comandos de corrección de actitud
    """
    # Errores de inclinación (diferencia entre lo deseado y lo actual)
    pitch_error = desired_pitch - actual_pitch
    pitch_deriv = (pitch_error - pid.past_pitch_error) / dt   # Derivada del error de pitch
    roll_error  = desired_roll  - actual_roll
    roll_deriv  = (roll_error  - pid.past_roll_error)  / dt   # Derivada del error de roll
    yaw_rate_error = desired_yaw_rate - actual_yaw_rate

    # Comandos PD para cada eje de rotación
    # Nota: pitch_cmd es negativo porque en Webots/Crazyflie el eje está invertido
    roll_cmd  =  KP_ATT_RP * constrain(roll_error,  -1, 1) + KD_ATT_RP * roll_deriv
    pitch_cmd = -KP_ATT_RP * constrain(pitch_error, -1, 1) - KD_ATT_RP * pitch_deriv
    yaw_cmd   =  KP_ATT_Y  * constrain(yaw_rate_error, -1, 1)

    # Guardar errores actuales para el siguiente paso
    pid.past_pitch_error    = pitch_error
    pid.past_roll_error     = roll_error
    pid.past_yaw_rate_error = yaw_rate_error

    return roll_cmd, pitch_cmd, yaw_cmd

def pid_horizontal_velocity_controller(actual_vx, actual_vy,
                                        desired_vx, desired_vy, dt):
    """
    Controlador PID de velocidad horizontal.
    Réplica de pid_horizontal_velocity_controller() en pid_controller.c

    Convierte errores de velocidad horizontal en ángulos de inclinación
    deseados. El dron se inclina hacia adelante para avanzar (pitch)
    y hacia los lados para moverse lateralmente (roll).

    Parámetros:
        actual_vx/vy  → velocidades actuales en el frame del cuerpo del dron
        desired_vx/vy → velocidades objetivo
        dt            → tiempo transcurrido (segundos)

    Retorna:
        pitch_desired → cuánto debe inclinarse hacia adelante/atrás
        roll_desired  → cuánto debe inclinarse hacia los lados
    """
    # Errores de velocidad en los ejes X e Y del frame del dron
    vx_error   = desired_vx - actual_vx
    vx_deriv   = (vx_error - pid.past_vx_error) / dt   # Derivada del error en X
    vy_error   = desired_vy - actual_vy
    vy_deriv   = (vy_error - pid.past_vy_error) / dt   # Derivada del error en Y

    # Convertir error de velocidad → ángulo de inclinación deseado
    pitch_desired = KP_VEL_XY * constrain(vx_error, -1, 1) + KD_VEL_XY * vx_deriv
    roll_desired  = -(KP_VEL_XY * constrain(vy_error, -1, 1) + KD_VEL_XY * vy_deriv)

    # Guardar errores para el siguiente paso
    pid.past_vx_error = vx_error
    pid.past_vy_error = vy_error

    return pitch_desired, roll_desired

def motor_mixing(altitude_cmd, roll_cmd, pitch_cmd, yaw_cmd):
    """
    Mezcla de motores: convierte los comandos PID en velocidades individuales.
    Réplica de motor_mixing() en pid_controller.c

    El Crazyflie tiene 4 motores en configuración X. Cada uno recibe
    una combinación diferente de los comandos para lograr el movimiento deseado:

        m1 (trasero-derecho): -roll +pitch +yaw
        m2 (trasero-izquierdo): -roll -pitch -yaw
        m3 (delantero-derecho): +roll -pitch +yaw
        m4 (delantero-izquierdo): +roll +pitch -yaw

    Los motores m1 y m3 giran en sentido contrario (velocidad negativa),
    m2 y m4 giran en sentido normal (velocidad positiva), según crazyflie.c.
    """
    # Calcular la potencia de cada motor combinando los 4 comandos
    m1 = altitude_cmd - roll_cmd + pitch_cmd + yaw_cmd
    m2 = altitude_cmd - roll_cmd - pitch_cmd - yaw_cmd
    m3 = altitude_cmd + roll_cmd - pitch_cmd + yaw_cmd
    m4 = altitude_cmd + roll_cmd + pitch_cmd - yaw_cmd

    # Aplicar velocidades con los signos correctos según crazyflie.c
    # max(0.0, ...) evita velocidades negativas (los motores no van en reversa)
    motores[0].setVelocity(-max(0.0, m1))   # m1: gira en reversa → velocidad negativa
    motores[1].setVelocity( max(0.0, m2))   # m2: gira normal → velocidad positiva
    motores[2].setVelocity(-max(0.0, m3))   # m3: gira en reversa → velocidad negativa
    motores[3].setVelocity( max(0.0, m4))   # m4: gira normal → velocidad positiva

def apagar_motores():
    """
    Detiene completamente todos los motores.
    Se llama cuando el dron aterriza (estado IDLE) o en emergencia.
    """
    for m in motores:
        m.setVelocity(0.0)

# ── 7. INICIALIZACIÓN DE WEBOTS ──────────────────────────────────────────────
# Crear el objeto Robot y obtener el timestep de la simulación
robot    = Robot()
timestep = int(robot.getBasicTimeStep())   # Período de cada paso en milisegundos
dt_step  = timestep / 1000.0              # Convertido a segundos

# Inicializar los 4 motores del Crazyflie
# setPosition(inf) = modo de control por velocidad (no por posición)
# Las velocidades iniciales ±1.0 son las mismas que en crazyflie.c
motores = []
velocidades_iniciales = [-1.0, 1.0, -1.0, 1.0]
for i, vi in enumerate(velocidades_iniciales, start=1):
    m = robot.getDevice(f"m{i}_motor")
    m.setPosition(float("inf"))   # Habilitar control de velocidad continua
    m.setVelocity(vi)             # Velocidad inicial (para romper inercia)
    motores.append(m)

# Inicializar sensores y habilitarlos con el timestep de la simulación
imu  = robot.getDevice("inertial_unit")   # Mide roll, pitch, yaw (orientación)
imu.enable(timestep)
gps  = robot.getDevice("gps")             # Mide posición X, Y, Z en el mundo
gps.enable(timestep)
gyro = robot.getDevice("gyro")            # Mide velocidades angulares (rad/s)
gyro.enable(timestep)

# Crear socket UDP no bloqueante para recibir datos del bridge (lecturas de
# suelo reenviadas + comandos de mision de la PWA)
# setblocking(False) permite que el bucle principal no se congele esperando datos
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

# Socket de salida para enviar telemetria real del dron de vuelta al bridge
telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telemetry_sock.setblocking(False)
last_telemetry_sent = 0.0

# ── 8. ESPERA DE INICIALIZACIÓN (igual que crazyflie.c) ──────────────────────
# El firmware original espera 2 segundos antes de comenzar a volar
# para que los sensores se estabilicen y el simulador se asiente.
print("=" * 60)
print("  CONTROLADOR SAGA — SISTEMA DE RIEGO AUTÓNOMO")
print("  Universidad Popular del Cesar")
print("  Esperando 2 segundos de inicialización...")
print("=" * 60)

while robot.step(timestep) != -1:
    if robot.getTime() > 2.0:
        break   # Salir del bucle de espera cuando pasen 2 segundos simulados

print("  Estado inicial: IDLE — Esperando datos de sensores...")

# ── 9. DEFINICIÓN DE ESTADOS ─────────────────────────────────────────────────
# Constantes de texto para identificar cada estado de la máquina de estados
IDLE      = "IDLE"       # En tierra, motores apagados, esperando orden
ASCENSO   = "ASCENSO"    # Subiendo verticalmente hasta ALTURA_OBJETIVO
NAVEGANDO = "NAVEGANDO"  # Volando horizontalmente hacia la zona objetivo
REGANDO   = "REGANDO"    # Hovering sobre la zona, aplicando riego
RETORNO   = "RETORNO"    # Volviendo a la posición base [0, 0]
DESCENSO  = "DESCENSO"   # Bajando controladamente hasta tocar tierra

# Variables de estado inicial
estado         = IDLE              # El dron comienza en tierra
objetivo_xy    = [0.0, 0.0]       # Coordenadas del destino actual
objetivo_zona  = None               # Nombre de zona objetivo actual (para telemetria)
timer_riego    = 0.0               # Contador de tiempo de riego acumulado
height_desired = ALTURA_OBJETIVO   # Altura objetivo dinámica (cambia en descenso)

# ── MODO DE OPERACION Y COLA DE MISION ───────────────────────────────────────
# El granjero controla el dron de 2 formas posibles (ver MissionControl.tsx):
#   "auto"   → el dron riega por su cuenta en cuanto la logica difusa detecta
#              una zona seca, sin esperar ningun boton. Este es el default.
#   "manual" → el dron SOLO despega cuando la PWA envia start_mission (boton).
# En cualquiera de los 2 modos, si al iniciar una mision otras zonas YA
# conocidas tambien estan secas, se encolan en cola_zonas para visitarlas
# todas antes de volver a la base (ver avanzar_a_siguiente_zona_o_retorno).
# Antes no existia esta distincion: la maquina de estados reaccionaba a CADA
# paquete de humedad que llegaba estando en IDLE sin importar si el granjero
# habia pedido control manual, y al terminar de regar una zona siempre volvia
# a la base ignorando cualquier otra zona seca, para luego re-despegar en
# cuanto aterrizaba y le llegaba el siguiente paquete de esa zona.
MODO_AUTO   = "auto"
MODO_MANUAL = "manual"
modo        = MODO_AUTO

cola_zonas     = []                              # zonas secas pendientes de esta mision
ultima_humedad = {z: None for z in COORDENADAS_ZONAS}  # cache: ultima lectura conocida por zona

# Nivel de agua estimado (no hay sensor real de tanque en la simulacion de
# Webots, se estima por tiempo de riego transcurrido). La bateria, en cambio,
# se reporta fija en 100% (ver enviar_telemetria): es una simulacion, no hay
# consumo real que estimar, y decrementarla artificialmente solo confundia.
nivel_agua_estimado = 100.0

# Mapeo de estados internos (mayusculas) al formato que espera la PWA
# (ver FlightStatus en src/lib/telemetry.ts)
ESTADO_A_FRONTEND = {
    IDLE: "idle",
    ASCENSO: "ascenso",
    NAVEGANDO: "navegando",
    REGANDO: "regando",
    RETORNO: "retorno",
    DESCENSO: "descenso",
}


# Anclas (x_metros_real, y_porcentaje_mapa) derivadas de COORDENADAS_ZONAS y
# ordenadas por X, en vez de constantes hardcodeadas por separado: si alguien
# cambia COORDENADAS_ZONAS (como paso al ajustar el mundo de Webots), esta
# proyeccion se actualiza sola. Antes esta funcion tenia sus propios numeros
# fijos (sur=-1.5, centro=0, norte=1.5) que quedaron desactualizados cuando
# COORDENADAS_ZONAS cambio a sur=-2.5/centro=1.7/norte=6.0, lo que hacia que
# CUALQUIER posicion con x cercana a la base (1.65) proyectara como si
# estuviera en el norte. Ese era el bug de "al volver a la base, el mapa
# muestra el dron en el norte".
_ANCLAS_X_PCT = sorted(
    [
        (COORDENADAS_ZONAS["sur"][0], 80.0),
        (COORDENADAS_ZONAS["centro"][0], 50.0),
        (COORDENADAS_ZONAS["norte"][0], 20.0),
    ],
    key=lambda par: par[0],
)


def proyectar_a_porcentaje(x_m: float, y_m: float):
    """Proyecta la coordenada X real de Webots (metros) al eje vertical
    porcentual 0-100 que usa el mapa de la PWA (ver ZONE_LAYOUT en
    src/components/MapContainer.tsx: sur=80%, centro=50%, norte=20%, todas en
    x=50%). Interpola linealmente entre las anclas conocidas y extrapola
    (recortando a [0,100]) para posiciones fuera de ese rango, como la base.
    NOTA: esto solo posiciona el icono en el mapa 2D simplificado de la PWA;
    la altitud real (metros) se envia por separado en enviar_telemetria, no
    se deriva de aqui.
    
    MEJORA: Si el dron está cerca de la base (x ≈ 1.65, y ≈ 6.32), retorna
    explícitamente su posición en el mapa (x=15%, y=50%), evitando que se
    interpole incorrectamente como si estuviera en centro."""
    
    # Caso especial: dron en la base (al oeste de centro, mismo Y que centro)
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
    """Construye y envia un paquete de telemetria real del dron hacia el
    bridge (ver procesar_telemetria_dron en udp_websocket_bridge.py)."""
    global nivel_agua_estimado

    # Bateria fija al 100%: esta es una simulacion en Webots, no hay una
    # bateria fisica que se consuma, asi que no tiene sentido decrementarla
    # (antes bajaba 0.02%/tick en cada paso de vuelo sin motivo real).
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
        # Altitud real en metros (independiente del "z" de arriba, que es
        # siempre 0 porque el mapa de la PWA es 2D). Antes no se enviaba
        # ningun campo separado para esto, asi que el frontend leia
        # drone.position.altitude (=el "z" del mapa, siempre 0) y por eso la
        # altitud nunca se actualizaba en la barra de telemetria.
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
    """Al terminar de regar una zona, revisa si quedan otras zonas secas
    pendientes en la cola de esta mision y navega hacia la siguiente en vez
    de volver a la base e ignorarlas (el dron aterrizaba, y recien ENTONCES
    detectaba la siguiente zona seca y volvia a despegar). Solo si la cola
    esta vacia se inicia el RETORNO real.
    
    MEJORA: 
    - En MODO AUTO: Re-evalúa todas las zonas para detectar si alguna se ha
      vuelto seca durante la misión.
    - En MODO MANUAL: Solo retorna a base sin buscar más zonas (el operador
      debe solicitar explícitamente cada zona)."""
    global objetivo_zona, objetivo_xy, estado, timer_riego, cola_zonas

    if cola_zonas:
        objetivo_zona = cola_zonas.pop(0)
        objetivo_xy = COORDENADAS_ZONAS.get(objetivo_zona, [0.0, 0.0])
        timer_riego = 0.0
        estado = NAVEGANDO
        print(f"  {motivo} Zonas pendientes en cola: siguiente → {objetivo_zona.upper()} "
              f"(quedan {len(cola_zonas)} despues de esta).")
    else:
        # Solo re-evaluar otras zonas en modo AUTO
        # En modo MANUAL, retornar directamente a base sin buscar más zonas
        if modo == MODO_AUTO:
            # Re-evaluar TODAS las zonas antes de retornar, en caso de que alguna
            # se haya vuelto seca durante el riego de las otras zonas
            zonas_secas_nuevas = [
                z for z, h in ultima_humedad.items()
                if h is not None and requiere_riego(h)
            ]
            
            if zonas_secas_nuevas:
                # Hay zonas que requieren riego → continuar con la misión
                objetivo_zona = zonas_secas_nuevas[0]
                objetivo_xy = COORDENADAS_ZONAS.get(objetivo_zona, [0.0, 0.0])
                cola_zonas = zonas_secas_nuevas[1:]  # Resto en cola
                timer_riego = 0.0
                estado = NAVEGANDO
                print(f"  {motivo} Nuevas zonas secas detectadas: {objetivo_zona.upper()} "
                      f"(cola: {cola_zonas or 'ninguna'})")
                return
        
        # Verdaderamente no hay más zonas que rieguen (o modo MANUAL) → retornar a base
        objetivo_xy = BASE_XY.copy()
        objetivo_zona = None
        estado = RETORNO
        print(f"  {motivo} No quedan zonas pendientes. Iniciando RETORNO (modo {modo.upper()}).")



# Leer posición inicial del GPS para calcular velocidades en el primer paso
past_x_global = gps.getValues()[0]
past_y_global = gps.getValues()[1]
past_time     = robot.getTime()

# ── 10. BUCLE PRINCIPAL DE CONTROL ───────────────────────────────────────────
# Este bucle se ejecuta en cada paso de simulación (cada `timestep` ms).
# En cada iteración: recibe datos UDP → lee sensores → ejecuta estado → aplica motores.
while robot.step(timestep) != -1:

    current_time = robot.getTime()
    dt = current_time - past_time
    if dt <= 0:
        dt = dt_step   # Protección contra división por cero en el primer paso

    # ── A. RECIBIR DATOS UDP (lecturas de suelo reenviadas + comandos de mision) ──
    # Intenta leer un paquete UDP. Si no hay datos, continúa sin bloquearse
    # (gracias a setblocking(False) → lanza BlockingIOError si no hay datos)
    try:
        data, _ = sock.recvfrom(4096)
        datos   = json.loads(data.decode("utf-8"))
        tipo    = datos.get("type")

        if tipo == "start_mission":
            # Comando explícito de la PWA (boton "Iniciar mision", modo
            # manual o auto): fuerza el despegue hacia la zona indicada, sin
            # esperar a que la lógica difusa lo active. Tambien encola
            # cualquier OTRA zona que, segun la ultima lectura conocida, siga
            # seca, para que la mision las atienda todas antes de volver.
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
                print(f"  [PWA] start_mission → zona {zona.upper()} "
                      f"(cola: {cola_zonas or 'ninguna'}). Iniciando ASCENSO.")

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
            # Alterna entre riego 100% autonomo ("auto") y solo-por-boton
            # ("manual"). No interrumpe una mision en curso, solo cambia como
            # reacciona el dron la proxima vez que este en IDLE.
            # Aceptar tanto "mode" (de la PWA en inglés) como "modo" (español)
            nuevo_modo = datos.get("mode") or datos.get("modo")
            if nuevo_modo in (MODO_AUTO, MODO_MANUAL) and nuevo_modo != modo:
                modo = nuevo_modo
                print(f"  [PWA] Modo cambiado a {modo.upper()}")

        elif "zona" in datos and "humedad" in datos:
            # Lectura de suelo reenviada por el bridge (sensor_nasa.py / sensor_mock.py)
            humedad = float(datos["humedad"])
            zona    = datos.get("zona", "centro")
            ultima_humedad[zona] = humedad

            # Solo se imprime cuando el dron esta parado evaluando si debe
            # despegar (o cuando efectivamente decide hacerlo). Antes se
            # imprimia una linea por CADA paquete de humedad sin importar el
            # estado, lo que inundaba la consola incluso a mitad de una
            # mision con lecturas de zonas que no le interesaban en ese
            # momento al dron.
            if estado == IDLE:
                print(f"  Zona {zona.upper()}: {humedad:.1f}% | IDLE, modo {modo.upper()}")

            # Reaccionar al paquete según el estado actual del dron
            if estado == IDLE:
                # Solo despega por su cuenta en modo AUTO. En modo MANUAL se
                # limita a actualizar ultima_humedad y esperar el boton.
                if modo == MODO_AUTO and requiere_riego(humedad):
                    objetivo_zona  = zona
                    objetivo_xy    = COORDENADAS_ZONAS.get(zona, [0.0, 0.0])
                    cola_zonas     = [
                        z for z, h in ultima_humedad.items()
                        if z != zona and h is not None and requiere_riego(h)
                    ]
                    height_desired = ALTURA_OBJETIVO
                    estado         = ASCENSO
                    print(f"  [AUTO] Riego requerido en {zona.upper()}. "
                          f"Iniciando ASCENSO → objetivo {objetivo_xy} "
                          f"(cola: {cola_zonas or 'ninguna'})")

            elif estado == REGANDO:
                # Si ya está regando y la humedad de la ZONA OBJETIVO (no de
                # cualquier otra zona que llegue en la ronda del sensor) se
                # normalizó → pasar a la siguiente zona pendiente (si hay) o
                # volver a casa.
                if zona == objetivo_zona and not requiere_riego(humedad):
                    avanzar_a_siguiente_zona_o_retorno(f"Zona {zona.upper()} ya no requiere riego.")

    except BlockingIOError:
        # No hay paquete UDP disponible en este paso → continuar normalmente
        pass
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # El paquete llegó corrupto o con formato incorrecto → ignorar y seguir
        print(f"  Paquete UDP malformado: {e}")


    # ── B. LEER SENSORES ─────────────────────────────────────────────────────
    # Obtener orientación actual del dron desde el IMU
    rpy = imu.getRollPitchYaw()
    actual_roll      = rpy[0]   # Inclinación lateral (eje X)
    actual_pitch     = rpy[1]   # Inclinación frontal (eje Y)
    actual_yaw_rate  = gyro.getValues()[2]   # Velocidad de giro sobre eje Z

    # Obtener posición 3D del GPS
    gps_vals        = gps.getValues()
    x_global        = gps_vals[0]   # Posición Este-Oeste en el mundo
    y_global        = gps_vals[1]   # Posición Norte-Sur en el mundo
    actual_altitude = gps_vals[2]   # Altura sobre el suelo

    # Calcular velocidades globales a partir del cambio de posición GPS
    # y convertirlas al frame del cuerpo del dron (rotando por el yaw actual)
    actual_yaw = imu.getRollPitchYaw()[2]
    vx_global  = (x_global - past_x_global) / dt   # Velocidad global en X
    vy_global  = (y_global - past_y_global) / dt   # Velocidad global en Y
    cosyaw = math.cos(actual_yaw)
    sinyaw = math.sin(actual_yaw)
    # Rotación al frame del cuerpo del dron:
    actual_vx =  vx_global * cosyaw + vy_global * sinyaw   # Velocidad frontal
    actual_vy = -vx_global * sinyaw + vy_global * cosyaw   # Velocidad lateral

    # ── C. MÁQUINA DE ESTADOS ────────────────────────────────────────────────

    if estado == IDLE:
        # ── IDLE: El dron está en tierra esperando ────────────────────────────
        # No hay vuelo → simplemente apagar motores en cada paso
        apagar_motores()

    else:
        # ── ESTADOS DE VUELO ─────────────────────────────────────────────────
        # Para cualquier estado que implique vuelo, se calcula el pipeline PID completo.
        # Las velocidades deseadas se modifican según el estado activo.

        # Por defecto: hover estático (sin movimiento, sin rotación)
        desired_vx    = 0.0
        desired_vy    = 0.0
        desired_yaw_r = 0.0

        # ── ASCENSO: Subir verticalmente sin moverse ──────────────────────────
        if estado == ASCENSO:
            desired_vx = 0.0
            desired_vy = 0.0
            # Verificar si ya alcanzó la altura de crucero
            error_z = height_desired - actual_altitude
            if abs(error_z) < TOLERANCIA_Z:
                print(f"  Altura {actual_altitude:.2f}m alcanzada. Transitando a NAVEGANDO")
                estado = NAVEGANDO   # Altura lista → empezar a moverse horizontalmente

        # ── NAVEGANDO: Volar horizontalmente hacia la zona objetivo ───────────
        elif estado == NAVEGANDO:
            # Calcular error de posición horizontal respecto al objetivo
            error_x = objetivo_xy[0] - x_global
            error_y = objetivo_xy[1] - y_global

            # Convertir error de posición en velocidad deseada (controlador P)
            # Limitada a ±0.5 m/s para vuelo suave y seguro
            desired_vx = constrain(error_x * KP_VEL_XY, -0.5, 0.5)
            desired_vy = constrain(error_y * KP_VEL_XY, -0.5, 0.5)

            # Verificar si llegó a la zona objetivo
            distancia_xy = math.sqrt(error_x**2 + error_y**2)
            if distancia_xy < TOLERANCIA_XY:
                print(f"  Zona alcanzada en ({x_global:.2f}, {y_global:.2f}). Iniciando RIEGO...")
                timer_riego = 0.0
                estado      = REGANDO   # Llegó → comenzar a regar

        # ── REGANDO: Hover estacionario sobre la zona mientras riega ─────────
        elif estado == REGANDO:
            # Mantener posición exacta sobre la zona (corrección suave)
            error_x    = objetivo_xy[0] - x_global
            error_y    = objetivo_xy[1] - y_global
            desired_vx = constrain(error_x * KP_VEL_XY, -0.3, 0.3)   # Más lento que navegando
            desired_vy = constrain(error_y * KP_VEL_XY, -0.3, 0.3)

            # Acumular tiempo de riego
            timer_riego += dt
            if timer_riego >= TIEMPO_RIEGO_S:
                # Tiempo de riego completado en esta zona → pasar a la
                # siguiente zona pendiente en cola, si hay, o volver a base.
                avanzar_a_siguiente_zona_o_retorno(f"Riego completado ({TIEMPO_RIEGO_S}s) en {objetivo_zona.upper()}.")

        # ── RETORNO: Volar de vuelta al punto de despegue [0, 0] ─────────────
        elif estado == RETORNO:
            error_x    = objetivo_xy[0] - x_global
            error_y    = objetivo_xy[1] - y_global
            desired_vx = constrain(error_x * KP_VEL_XY, -0.5, 0.5)
            desired_vy = constrain(error_y * KP_VEL_XY, -0.5, 0.5)

            # Verificar si llegó a la base
            distancia_xy = math.sqrt(error_x**2 + error_y**2)
            if distancia_xy < TOLERANCIA_XY:
                print(f"  Base alcanzada. Iniciando DESCENSO")
                pid.altitude_integrator = 0.0
                pid.past_altitude_error = 0.0
                estado = DESCENSO   # Llegó a casa → comenzar a bajar

        # ── DESCENSO: Bajar controladamente hasta tocar tierra ────────────────
        elif estado == DESCENSO:
            # Reducir la altura deseada gradualmente (0.3 m/s de descenso)
            height_desired -= 0.15 * dt
            height_desired = max(0.0, height_desired)
            desired_vx     = 0.0   # Sin movimiento horizontal durante el descenso
            desired_vy     = 0.0

            # Detectar aterrizaje: GPS reporta altura menor al umbral de suelo
            if actual_altitude < ALTURA_SUELO:
                print("  Dron aterrizado. Volviendo a IDLE")
                apagar_motores()
                estado = IDLE
                objetivo_zona = None
                # Actualizar referencias para el próximo ciclo
                past_time     = current_time
                past_x_global = x_global
                past_y_global = y_global
                continue   # Saltar el pipeline PID en este paso (ya aterrizó)

        # ── PIPELINE PID COMPLETO ─────────────────────────────────────────────
        # Se ejecuta en todos los estados de vuelo. Sigue la misma estructura
        # que pid_velocity_fixed_height_controller() en pid_controller.c:

        # Paso 1: Error de velocidad → inclinación deseada (roll/pitch)
        pitch_desired, roll_desired = pid_horizontal_velocity_controller(
            actual_vx, actual_vy, desired_vx, desired_vy, dt
        )
        
        pitch_desired = constrain(pitch_desired, -0.15, 0.15)
        roll_desired  = constrain(roll_desired, -0.15, 0.15)

        # Paso 2: Error de altura → comando de empuje total
        altitude_cmd = pid_fixed_height_controller(actual_altitude, height_desired, dt)

        # Paso 3: Error de actitud → comandos de corrección de orientación
        roll_cmd, pitch_cmd, yaw_cmd = pid_attitude_controller(
            actual_roll, actual_pitch, actual_yaw_rate,
            roll_desired, pitch_desired, desired_yaw_r, dt
        )

        # Paso 4: Mezclar comandos y aplicar velocidades a cada motor
        motor_mixing(altitude_cmd, roll_cmd, pitch_cmd, yaw_cmd)

    # ── D. ACTUALIZAR REFERENCIAS TEMPORALES ─────────────────────────────────
    # Guardar tiempo y posición actuales para calcular velocidades en el próximo paso
    past_time     = current_time
    past_x_global = x_global
    past_y_global = y_global

    # ── E. TELEMETRIA REAL HACIA EL BRIDGE (~1 Hz) ───────────────────────────
    # Reporta posicion/altura/bateria/estado reales de esta simulacion Webots;
    # la PWA los recibe fusionados con las lecturas de suelo (ver
    # udp_websocket_bridge.py). No se envia en cada paso de simulacion (que
    # corre a decenas de Hz) para no saturar el enlace; se limita a ~1 Hz,
    # igual que el resto del pipeline.
    if current_time - last_telemetry_sent >= TELEMETRY_INTERVAL_S:
        speed_mps = math.sqrt(vx_global ** 2 + vy_global ** 2)
        enviar_telemetria(x_global, y_global, actual_altitude, speed_mps)
        last_telemetry_sent = current_time
