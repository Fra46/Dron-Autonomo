# 🚁 AgroDrone - Sistema de Riego Autónomo

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

> Proyecto desarrollado por el equipo **ACEIS** (Asociación Centro de Estudios de Ingeniería de Sistemas) de la **Universidad Popular del Cesar**.
>
> Este trabajo fue creado para competir en el evento **20CCC Cartagena 2026**, que se realizará del **12 al 14 de agosto de 2026**.

Sistema completo de riego agrícola autónomo que combina un dron Mavic 2 Pro con sensores de humedad del suelo, procesamiento de datos en tiempo real y una interfaz web progresiva (PWA) para monitoreo y control remoto.

## 🌟 Características Principales

- **🛰️ Monitoreo en Tiempo Real**: Sensores de humedad conectados vía UDP con actualización continua
- **🤖 Control Autónomo**: Dron que responde automáticamente a niveles críticos de humedad
- **📱 Interfaz Web Moderna**: PWA responsive con mapas interactivos y telemetría en vivo
- **🔄 Comunicación Bidireccional**: WebSocket para comandos en tiempo real desde la interfaz
- **📊 Visualización Avanzada**: Mapas con zonas de cultivo, niveles de humedad y estado del dron
- **🌍 Datos Satelitales**: Integración opcional con datos SMAP de la NASA
- **🎯 Lógica Difusa**: Sistema inteligente de toma de decisiones para riego

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐                                   ┌──────────────────┐    WebSocket (8765)      ┌──────────────┐
│  sensor_nasa.py │ ── UDP 5005 (lectura de suelo) ─► │  udp_websocket   │ ◄──────────────────────► │     PWA      │
│  sensor_mock.py │                                   │    _bridge.py    │   (snapshot agregado     │  (Frontend)  │
└─────────────────┘                                   │  (agregador con  │   + comandos de mision)  └──────────────┘
                                                      │     estado)      │
┌─────────────────┐                                   │                  │
│ mavic_          │ ── UDP 5005 (drone_telemetry) ──► │                  │
│ controller.py   │ ◄─ UDP 5006 (lecturas + cmds) ──  └──────────────────┘
│ (Webots/Dron)   │
└─────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────────────┐
│                       Webots Simulation Environment                     │
└─────────────────────────────────────────────────────────────────────────┘
```

El bridge fusiona ambas fuentes (humedad de suelo + telemetría real del dron) en
un único snapshot `telemetry_update` (ver `docs/TELEMETRY.md`), y reenvía los
comandos de misión que la PWA envía por WebSocket (`start_mission`,
`stop_mission`, `emergency_stop`, `request_status`) hacia el controlador por UDP.

### Componentes del Sistema

| Componente | Tecnología | Función |
|------------|------------|---------|
| **Frontend PWA** | React + TypeScript + Vite | Interfaz de usuario y control |
| **Bridge UDP-WebSocket** | Python + WebSockets | Puente de comunicación |
| **Simulador de Sensores** | Python | Datos de humedad simulados |
| **Sensor NASA SMAP** | Python + EarthAccess | Datos satelitales reales |
| **Controlador Mavic (Webots)** | Python + Webots API | Control del dron físico en simulación |

## 🛠️ Tecnologías Utilizadas

### Frontend
- **React 19** - Framework UI moderno
- **TypeScript** - Tipado estático
- **Vite** - Build tool ultrarrápido
- **Bootstrap 5** - Framework CSS responsive
- **Lucide React** - Iconos modernos

### Backend & Scripts
- **Python 3.8+** - Scripts de simulación y puente
- **WebSockets** - Comunicación bidireccional
- **UDP Sockets** - Comunicación con sensores
- **EarthAccess** - API de datos NASA

### Simulación
- **Webots** - Entorno de simulación robótica
- **Mavic 2 Pro (Webots model)** - Control del dron

## 🚀 Instalación y Configuración

### Prerrequisitos

- **Node.js** 18+ y **npm** (o pnpm/yarn si prefieren, pero el lockfile commiteado es de npm)
- **Python** 3.8+ con pip
- **Webots** (opcional, para simulación completa)

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Fra46/Dron-Autonomo.git
```

### 2. Instalar Dependencias del Frontend

```bash
# Instalar dependencias de Node.js
npm install
```

### 3. Configurar Scripts Python

```bash
# Instalar dependencias de Python
pip install websockets

# Para datos satelitales de NASA
pip install earthaccess h5py numpy
```

### 📖 Configuración de Credenciales NASA (Importante ⭐)

Para usar **datos reales del satélite SMAP de NASA** con `scripts/sensor_nasa.py`,
se debe guardar el token de Earthdata en el almacén seguro del sistema usando
`keyring`.

1. Crea una cuenta y obtén tu token en:
   https://urs.earthdata.nasa.gov/home

2. Instala `keyring`:

```powershell
python -m pip install keyring
```

3. Guarda tu token en el keyring:

```powershell
python scripts/set_earthdata_token.py "TU_TOKEN_AQUI"
```

El script almacena el token en el servicio `earthdata` con usuario `token`.
`python scripts/sensor_nasa.py` lo lee automáticamente del keyring.

Si no configuras el token en el keyring o si la conexión remota a NASA falla,
el sistema cae automáticamente a un fallback simulado sin interrumpir el flujo
de telemetría.

### 4. Configurar Webots

1. Instalar [Webots R2023b+](https://cyberbotics.com/)
2. Abrir el proyecto de Webots incluido en `AgroDrone-Webots/`
3. Abrir el mundo final `AgroDrone-Webots/worlds/AgroDrone4.wbt`
4. Seleccionar el robot y asignar el controlador `AgroDrone-Webots/controllers/mavic_controller/mavic_controller.py`
5. Iniciar la simulación para que el controlador envíe telemetría al bridge UDP/WebSocket

> 📌 Nota: la simulación final del proyecto es `AgroDrone4.wbt` y el controlador principal usado en la versión de entrega es `mavic_controller.py`.

## 📖 Uso

### Inicio Rápido 🚀

**Terminal 1 — Bridge UDP-WebSocket:**
```bash
cd scripts
python udp_websocket_bridge.py
```

**Terminal 2 — Sensor de datos (fuente principal: NASA SMAP):**
```bash
# Opción A (recomendada): datos reales del satélite NASA SMAP
# Requiere token de Earthdata guardado en keyring — ver "Configuración de Credenciales NASA" arriba.
python sensor_nasa.py
# → Si no hay token en keyring o falla la conexión remota, cae automáticamente
#   a un fallback simulado compatible, sin detener el flujo de telemetría.

# Opción B: simulador puro, útil solo para desarrollo rápido sin red/credenciales
python sensor_mock.py
```

**Terminal 3 — Simulación del dron (Webots):**
```bash
# Abrir el mundo de Webots y cargar mavic_controller.py como controlador
# del robot. Emite telemetría real (posición, batería estimada, estado de
# la máquina de estados) de vuelta al bridge en el puerto 5005.
```

**Terminal 4 — PWA Frontend:**
```bash
# En la raíz del proyecto
npm run dev -- --host
```

> 📱 Para usar la PWA desde el teléfono, ejecuta `npm run dev -- --host` y abre
> `http://<IP-del-PC>:3000` desde el navegador del dispositivo en la misma red.

### Modos de Operación

| Modo | Comando | Datos | Velocidad | Requisitos |
|------|---------|-------|-----------|-----------|
| **NASA SMAP Real** (recomendado) | `sensor_nasa.py` | Satélite real, con fallback simulado integrado | 🐢 Lento (1a) | Token Earthdata en keyring |
| **Simulación** | `sensor_mock.py` | Aleatorios realistas | ⚡ Rápido | Ninguno |
| **Simulación Completa** | Webots + `mavic_controller.py` | Física realista + telemetría real del dron | 🐢 Muy lento | Webots instalado |

✅ **Nota:** Si `sensor_nasa.py` no tiene credenciales o falla la conexión remota, **automáticamente cambia a datos simulados** sin interrumpir el flujo de telemetría hacia la PWA.

## 📁 Estructura del Proyecto

```
agrodron-autonomo/
├── 📁 src/
│   ├── main.tsx               # Entry point (Vite)
│   ├── App.tsx                # Componente raíz
│   ├── components/            # Componentes React (TelemetryBar, MapContainer, ScorePanel, BigScoreSummary, MissionControl)
│   ├── contexts/
│   │   └── TelemetryContext.tsx
│   ├── hooks/
│   │   └── use-telemetry.ts
│   ├── lib/                   # telemetry.ts, telemetrySocket.ts, commands.ts, uiUtils.ts
│   └── styles/
│       └── globals.css
├── 📁 public/                 # Archivos estáticos e íconos PWA
│   └── manifest.json
├── 📁 scripts/                 # Scripts Python (backend/simulación)
│   ├── sensor_mock.py
│   ├── sensor_nasa.py
│   ├── udp_websocket_bridge.py
│   ├── mavic_controller.py
│   └── measure_bridge_latency.py   # Mide latencia real UDP → WebSocket
├── 📁 docs/
│   └── TELEMETRY.md           # Documentación detallada del protocolo de telemetría
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── README.md
```

## 🎮 Scripts Disponibles

### Scripts Python

| Script | Comando | Descripción |
|--------|---------|-------------|
| `sensor_mock.py` | `python sensor_mock.py` | Simula sensores de humedad |
| `sensor_nasa.py` | `python sensor_nasa.py` | Descarga datos reales NASA SMAP |
| `udp_websocket_bridge.py` | `python udp_websocket_bridge.py` | Puente UDP ↔ WebSocket |
| `mavic_controller.py` | `python mavic_controller.py` | Controlador del dron Webots |
| `measure_bridge_latency.py` | `python measure_bridge_latency.py --samples 300` | Mide la latencia real extremo a extremo UDP → WebSocket (requiere el bridge corriendo) |

### Scripts NPM

| Comando | Descripción |
|---------|-------------|
| `npm run dev` | Inicia servidor de desarrollo |
| `npm run build` | Construye para producción |
| `npm run preview` | Vista previa de producción |

## 🔧 Configuración

### Variables de Entorno

Crear archivo `.env.local`:

```env
# Puerto del servidor de desarrollo
VITE_PORT=3000

# Configuración WebSocket (opcional, por defecto localhost:8765)
VITE_WS_HOST=localhost
VITE_WS_PORT=8765
```

### Puertos Utilizados

| Servicio | Puerto | Protocolo | Dirección |
|----------|--------|-----------|-----------|
| Frontend PWA | 3000 | HTTP | — |
| Puente WebSocket | 8765 | WebSocket | Bridge ↔ PWA |
| Bridge — entrada de telemetría | 5005 | UDP | Sensores de suelo → Bridge, Dron → Bridge |
| Bridge — salida al controlador | 5006 | UDP | Bridge → `mavic_controller.py` (lecturas reenviadas + comandos de misión) |
| Webots (opcional) | 1999 | TCP | — |

> ⚠️ Importante: 5005 y 5006 son puertos distintos a propósito. Si ambos procesos
> (`udp_websocket_bridge.py` y `mavic_controller.py` en Webots) intentaran
> escuchar en el mismo puerto UDP en la misma máquina, uno de los dos fallaría
> al iniciar (`Address already in use`).

## 🎯 Estados del Sistema

### Estados del Dron

| Estado | Descripción |
|--------|-------------|
| `idle` | En tierra, esperando órdenes |
| `ascenso` | Subiendo a altura de crucero |
| `navegando` | Viajando a zona objetivo |
| `regando` | Aplicando riego en zona |
| `retorno` | Regresando a base |
| `descenso` | Aterrizando |

### Comandos de Misión

Implementados exactamente como se describen en el paper (sección 2.4), enviados
por la PWA vía WebSocket y reenviados por el bridge al controlador por UDP:

| Comando | Botón en la PWA | Efecto |
|---------|-----------------|--------|
| `start_mission` | "Iniciar misión a \<zona\>" | `idle → ascenso`, con zona objetivo asignada |
| `stop_mission` | "Detener Misión" | Detiene la misión activa y ordena retorno a base |
| `emergency_stop` | "Parada de emergencia" | Transición inmediata a descenso seguro |
| `request_status` | "Sincronizar estado" | Solicita sincronización inmediata de telemetría |

### Lógica Difusa de Activación de Riego

Implementada en `mavic_controller.py` exactamente como en las ecuaciones
(1)-(3) del paper: se activa una misión cuando `μ_dry(h) + μ_very_dry(h) > θ`,
con `θ = 0.35` en la implementación actual (el paper, Tabla 2, especifica
+`θ = 0.65`; se redujo para activar riego preventivo en niveles de humedad
+medios — ver comentario en `mavic_controller.py`).

### Niveles de Humedad (color de interfaz)

Nota: esta escala LV0-LV5 es solo para la visualización de color en la PWA
(no es el mismo umbral que la lógica difusa de activación de riego, arriba).

| Nivel | Rango | Estado | Color | Acción |
|-------|-------|--------|-------|--------|
| LV0 | 0-25% | Crítico | 🔴 Rojo | Riego urgente |
| LV1 | 25-40% | Bajo | 🟠 Naranja | Riego necesario |
| LV2 | 40-55% | Moderado | 🟡 Amarillo | Monitorear |
| LV3 | 55-70% | Óptimo | 🟢 Verde | OK |
| LV4 | 70-85% | Alto | 🔵 Cyan | OK |
| LV5 | 85-100% | Saturado | 🟣 Púrpura | Exceso |

## 🤝 Contribución


1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

### Guías de Desarrollo

- Usar TypeScript para todo el código nuevo
- Seguir convenciones de nomenclatura camelCase
- Mantener cobertura de tipos > 90%
- Documentar funciones complejas
- Usar ESLint y Prettier

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## 🙏 Agradecimientos

- **ACEIS** - Asociación Centro de Estudios de Ingeniería de Sistemas, Universidad Popular del Cesar
- **Universidad Popular del Cesar** - Institución educativa
- **NASA SMAP** - Datos satelitales de humedad del suelo
- **DJI** - Mavic 2 Pro drone platform
- **Cyberbotics** - Webots simulation software

---

⭐ **Si este proyecto te resulta útil, ¡dale una estrella!**</content>
<filePath>README.md
