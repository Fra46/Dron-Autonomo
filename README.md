# 🚁 AgroDrone - Sistema de Riego Autónomo

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

> Proyecto desarrollado por el equipo **ACEIS** (Asociación Centro de Estudios de Ingeniería de Sistemas)
> de la **Universidad Popular del Cesar**.

Sistema completo de riego agrícola autónomo que combina un dron Crazyflie con sensores de humedad del suelo, procesamiento de datos en tiempo real y una interfaz web progresiva (PWA) para monitoreo y control remoto.

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
┌─────────────────┐     UDP (5005)      ┌──────────────────┐     WebSocket (8765)    ┌──────────────┐
│  sensor_mock.py │ ──────────────────► │  udp_websocket   │ ◄────────────────────► │     PWA      │
│  sensor_nasa.py │                     │    _bridge.py    │                         │  (Frontend)  │
└─────────────────┘                     └──────────────────┘                         └──────────────┘
        │                                       ▲                                       │
        │                                       │                                       │
        ▼                                       │                                       │
┌─────────────────┐                             │                                       │
│ crazyflie_      │ ◄───────────────────────────┘                                       │
│ controller.py   │   (Lee mismos datos UDP en Webots)                                  │
│ (Webots/Dron)   │                                                                       │
└─────────────────┘                                                                       │
                                                                                          │
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Webots Simulation Environment                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Componentes del Sistema

| Componente | Tecnología | Función |
|------------|------------|---------|
| **Frontend PWA** | React + TypeScript + Vite | Interfaz de usuario y control |
| **Bridge UDP-WebSocket** | Python + WebSockets | Puente de comunicación |
| **Simulador de Sensores** | Python | Datos de humedad simulados |
| **Sensor NASA SMAP** | Python + EarthAccess | Datos satelitales reales |
| **Controlador Crazyflie** | Python + Webots API | Control del dron físico |

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
- **Crazyflie Python API** - Control del dron

## 🚀 Instalación y Configuración

### Prerrequisitos

- **Node.js** 18+ y **pnpm**
- **Python** 3.8+ con pip
- **Webots** (opcional, para simulación completa)

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/agrodron-autonomo.git
cd agrodron-autonomo
```

### 2. Instalar Dependencias del Frontend

```bash
# Instalar dependencias de Node.js
pnpm install

# Iniciar servidor de desarrollo
pnpm dev
```

La PWA estará disponible en `http://localhost:3000`

### 3. Configurar Scripts Python

```bash
# Instalar dependencias de Python
pip install websockets

# Para datos satelitales de NASA (opcional)
pip install earthaccess h5py numpy
```

### 4. Configurar Webots (Opcional)

1. Instalar [Webots R2023b+](https://cyberbotics.com/)
2. Abrir el proyecto de Webots incluido
3. Configurar el controlador `crazyflie_controller.py`

## 📖 Uso

### Inicio Rápido

1. **Iniciar el Puente UDP-WebSocket:**
   ```bash
   cd scripts
   python udp_websocket_bridge.py
   ```

2. **Iniciar Simulador de Sensores:**
   ```bash
   # Terminal separado
   python sensor_mock.py
   ```

3. **Abrir la PWA:**
   - Navegar a `http://localhost:3000`
   - La interfaz se conectará automáticamente al WebSocket

### Modos de Operación

#### Modo Simulación (Predeterminado)
- Si no hay conexión UDP, la PWA entra automáticamente en modo SIM
- Genera datos aleatorios para testing

#### Modo Datos Reales
- Con `sensor_mock.py`: Datos simulados realistas
- Con `sensor_nasa.py`: Datos satelitales SMAP de la NASA

#### Modo Simulación Completa
- Webots + Crazyflie controller para simulación física

## 📁 Estructura del Proyecto

```
agrodron-autonomo/
├── 📁 app/                    # Next.js App Router
│   ├── globals.css           # Estilos globales
│   ├── layout.tsx            # Layout principal
│   └── page.tsx              # Página principal
├── 📁 components/            # Componentes React
│   ├── ui/                   # Componentes UI reutilizables
│   ├── drone/                # Componentes específicos del dron
│   └── theme-provider.tsx    # Proveedor de tema
├── 📁 contexts/              # Contextos React
│   └── TelemetryContext.tsx  # Contexto de telemetría
├── 📁 hooks/                 # Hooks personalizados
├── 📁 lib/                   # Utilidades y configuraciones
├── 📁 public/                # Archivos estáticos
│   ├── manifest.json         # Configuración PWA
│   └── icons/                # Iconos de la app
├── 📁 scripts/               # Scripts Python
│   ├── sensor_mock.py        # Simulador de sensores
│   ├── sensor_nasa.py        # Datos NASA SMAP
│   ├── udp_websocket_bridge.py # Puente de comunicación
│   ├── crazyflie_controller.py # Controlador del dron
│   └── README_TELEMETRY.md   # Documentación detallada
├── 📁 styles/                # Estilos adicionales
├── package.json              # Dependencias Node.js
├── vite.config.ts           # Configuración Vite
├── tsconfig.json            # Configuración TypeScript
└── README.md                # Este archivo
```

## 🎮 Scripts Disponibles

### Scripts Python

| Script | Comando | Descripción |
|--------|---------|-------------|
| `sensor_mock.py` | `python sensor_mock.py` | Simula sensores de humedad |
| `sensor_nasa.py` | `python sensor_nasa.py` | Descarga datos reales NASA SMAP |
| `udp_websocket_bridge.py` | `python udp_websocket_bridge.py` | Puente UDP ↔ WebSocket |
| `crazyflie_controller.py` | `python crazyflie_controller.py` | Controlador del dron Webots |

### Scripts NPM

| Comando | Descripción |
|---------|-------------|
| `pnpm dev` | Inicia servidor de desarrollo |
| `pnpm build` | Construye para producción |
| `pnpm preview` | Vista previa de producción |

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

| Servicio | Puerto | Protocolo |
|----------|--------|-----------|
| Frontend PWA | 3000 | HTTP |
| Puente WebSocket | 8765 | WebSocket |
| Sensores UDP | 5005 | UDP |
| Webots (opcional) | 1999 | TCP |

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

### Niveles de Humedad

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
- **Bitcraze AB** - Crazyflie drone platform
- **Cyberbotics** - Webots simulation software

## 📞 Contacto

**ACEIS - Asociación Centro de Estudios de Ingeniería de Sistemas**
- Proyecto: Sistema de Riego Autónomo con Drones
- Email: [contacto@unicesar.edu.co](mailto:contacto@unicesar.edu.co)
- GitHub: [@unicesar](https://github.com/unicesar)

---

⭐ **Si este proyecto te resulta útil, ¡dale una estrella!**</content>
<filePath>README.md