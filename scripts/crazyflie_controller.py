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
import socket                  # Para recibir datos UDP del sensor NASA
import json                    # Para parsear los paquetes JSON que llegan por UDP
import math                    # Para operaciones trigonométricas (cos, sin, sqrt)

# ── 1. CONFIGURACIÓN DE RED ──────────────────────────────────────────────────
# El controlador escucha en TODAS las interfaces de red ("0.0.0.0")
# en el puerto 5005, esperando paquetes JSON del sensor_nasa.py
UDP_IP   = "0.0.0.0"
UDP_PORT = 5005

# ── 2. PARÁMETROS DE VUELO ───────────────────────────────────────────────────
ALTURA_OBJETIVO = 1.0    # Altura de crucero en metros (el dron vuela a esta altura)
ALTURA_SUELO    = 0.05   # Si el GPS marca menos de 5cm, se considera que aterrizó

# Márgenes de error aceptables para considerar que llegó al destino
TOLERANCIA_XY  = 0.15    # metros — tolerancia horizontal (llegar a la zona)
TOLERANCIA_Z   = 0.05    # metros — tolerancia vertical (alcanzar la altura de crucero)

# Cuántos segundos (simulados) riega el dron antes de volver a casa
TIEMPO_RIEGO_S = 10.0

# Posiciones físicas (X, Y) dentro del mundo 3D de Webots para cada zona del Cesar
# Estas coordenadas corresponden a norte, centro y sur del área monitoreada
COORDENADAS_ZONAS = {
    "norte":  [ 1.5,  1.5],
    "centro": [ 0.0,  0.0],
    "sur":    [-1.5, -1.5],
}

# ── 3. GANANCIAS PID ─────────────────────────────────────────────────────────
# Estas ganancias son idénticas a las del archivo crazyflie.c original de Webots.
# Cambiarlas afecta la estabilidad y velocidad de respuesta del dron.

# Controlador de actitud (orienta el dron: roll y pitch)
KP_ATT_RP  = 0.5    # Cuánto corrige el ángulo de inclinación (roll/pitch)
KD_ATT_RP  = 0.1    # Amortigua oscilaciones en la inclinación
KP_ATT_Y   = 1.0    # Cuánto corrige la rotación sobre el eje vertical (yaw)
KD_ATT_Y   = 0.5    # Amortigua oscilaciones en la rotación (no se usa actualmente)

# Controlador de velocidad horizontal (cuánto se inclina para moverse)
KP_VEL_XY  = 2.0    # Ganancia proporcional de velocidad horizontal
KD_VEL_XY  = 0.5    # Amortigua cambios bruscos de velocidad horizontal

# Controlador de altura (mantiene o cambia la altitud del dron)
KP_Z       = 10.0   # Responde agresivamente a errores de altura
KI_Z       = 5.0    # Elimina el error estático acumulado en altura
KD_Z       = 5.0    # Amortigua las oscilaciones verticales

# Empuje base en hover: valor constante que compensa la gravedad
# (viene hardcoded como "+48" en pid_controller.c del firmware original)
THRUST_BASE = 48.0

# ── 4. LÓGICA DIFUSA ─────────────────────────────────────────────────────────
# La lógica difusa permite tomar decisiones graduales en lugar de
# simples umbrales on/off. Se evalúa cuánto "pertenece" un valor
# a las categorías "muy seco" y "seco".

def mu_muy_seco(h):
    """
    Función de membresía difusa para 'suelo MUY SECO'.
    Retorna 1.0 (certeza total) si humedad <= 15%.
    Retorna 0.0 si humedad >= 30%.
    Entre 15% y 30% disminuye linealmente.
    """
    if h <= 15:
        return 1.0
    return max(0.0, (30 - h) / 15.0)

def mu_seco(h):
    """
    Función de membresía difusa para 'suelo SECO'.
    Tiene forma triangular: sube de 20% a 35%, baja de 35% a 50%.
    El pico (1.0) está en 35% de humedad.
    """
    if 20 < h <= 35:
        return (h - 20) / 15.0
    if 35 < h <= 50:
        return (50 - h) / 15.0
    return 0.0

def requiere_riego(humedad: float) -> bool:
    """
    Decide si una zona necesita riego usando lógica difusa.
    Suma los grados de pertenencia a 'muy_seco' y 'seco'.
    Si la suma supera 0.5 → se activa el riego.
    Esto evita activar el dron por lecturas ruidosas o valores límite.
    """
    return (mu_muy_seco(humedad) + mu_seco(humedad)) > 0.5

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

# Crear socket UDP no bloqueante para recibir datos del sensor_nasa.py
# setblocking(False) permite que el bucle principal no se congele esperando datos
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

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
timer_riego    = 0.0               # Contador de tiempo de riego acumulado
height_desired = ALTURA_OBJETIVO   # Altura objetivo dinámica (cambia en descenso)

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

    # ── A. RECIBIR DATOS UDP DEL SENSOR NASA ─────────────────────────────────
    # Intenta leer un paquete UDP. Si no hay datos, continúa sin bloquearse
    # (gracias a setblocking(False) → lanza BlockingIOError si no hay datos)
    try:
        data, _ = sock.recvfrom(4096)
        datos   = json.loads(data.decode("utf-8"))
        humedad = float(datos["humedad"])          # Porcentaje de humedad del suelo
        zona    = datos.get("zona", "centro")      # Norte, centro o sur

        print(f"  UDP recibido → Zona: {zona.upper()} | "
              f"Humedad: {humedad:.1f}% | Estado actual: {estado}")

        # Reaccionar al paquete según el estado actual del dron
        if estado == IDLE:
            # Si está en tierra y la humedad es crítica → despegar hacia esa zona
            if requiere_riego(humedad):
                objetivo_xy    = COORDENADAS_ZONAS.get(zona, [0.0, 0.0])
                height_desired = ALTURA_OBJETIVO
                estado         = ASCENSO
                print(f"  Riego requerido en {zona.upper()}. "
                      f"Iniciando ASCENSO → objetivo {objetivo_xy}")

        elif estado == REGANDO:
            # Si ya está regando y la humedad se normalizó → volver a casa
            if not requiere_riego(humedad):
                print(f"  Zona {zona.upper()} ya no requiere riego. Iniciando RETORNO.")
                objetivo_xy = [0.0, 0.0]
                estado      = RETORNO

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
                # Tiempo de riego completado → iniciar regreso a base
                print(f"  Riego completado ({TIEMPO_RIEGO_S}s). Iniciando RETORNO")
                objetivo_xy = [0.0, 0.0]   # La base está en el origen [0, 0]
                estado      = RETORNO

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
                estado = DESCENSO   # Llegó a casa → comenzar a bajar

        # ── DESCENSO: Bajar controladamente hasta tocar tierra ────────────────
        elif estado == DESCENSO:
            # Reducir la altura deseada gradualmente (0.3 m/s de descenso)
            height_desired = max(0.0, actual_altitude - 0.3 * dt)
            desired_vx     = 0.0   # Sin movimiento horizontal durante el descenso
            desired_vy     = 0.0

            # Detectar aterrizaje: GPS reporta altura menor al umbral de suelo
            if actual_altitude < ALTURA_SUELO:
                print("  Dron aterrizado. Volviendo a IDLE")
                apagar_motores()
                estado = IDLE
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
