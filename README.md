# FinTrack — App Python

Aplicación web de finanzas personales construida con **Dash + Plotly + PostgreSQL (Supabase)**, con un bot de **Telegram** para cargar transacciones y funcionalidades de **IA (Groq)** para transcripción de voz, extracción de transacciones, evaluación del perfil de inversor y generación de reportes mensuales.

---

## Estructura

```
finanzas_personales/
├── app.py                 ← Aplicación principal (UI Dash + callbacks + rutas Flask de audio)
├── bot.py                 ← Bot de Telegram (carga de transacciones por texto/voz)
├── database.py            ← Capa de acceso a datos (PostgreSQL / Supabase)
├── analytics.py           ← KPIs, alertas de liquidez, recordatorios, proyecciones, recomendaciones
├── investor_profile.py    ← Test de perfil de inversor (preguntas, puntuación, evaluación IA)
├── groq_utils.py          ← Integración con Groq (transcripción Whisper + generación de texto)
├── excel_report.py        ← Generador del reporte mensual en Excel (.xlsx)
├── requirements.txt       ← Dependencias Python
├── Procfile.txt           ← Comando de arranque para despliegue (Render)
└── .env.example           ← Plantilla de variables de entorno
```

---

## Instalación

```bash
# 1. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno (copiar .env.example a .env y completar)
cp .env.example .env

# 4. Ejecutar la aplicación (levanta la web Y el bot de Telegram en paralelo)
python app.py
```

Acceder en el navegador: **http://localhost:8050**


### Variables de entorno requeridas (`.env`)

| Variable | Uso |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexión a PostgreSQL (Supabase) |
| `GROQ_API_KEY` | Transcripción de audio, extracción de transacciones, reporte IA y evaluación del test de inversor |
| `TELEGRAM_BOT_TOKEN` | Bot de Telegram para carga de transacciones |

---

## Funcionalidades

### 🔐 Autenticación multiusuario
- Registro e inicio de sesión con contraseña (hasheada con `bcrypt`).
- Recuperación de contraseña mediante pregunta de seguridad configurable.
- Cada usuario tiene sus propias categorías, transacciones y perfil de inversor.

### 📊 Dashboard
- 4 KPI cards: Restante del mes, Ingresos, Gastos, Tasa de ahorro.
- Gráfico de barras: Ingresos vs Gastos por mes.
- Gráfico de torta: Gastos por rubro (mes actual).
- **Evolución del balance con simulador de tasa de ahorro**: el gráfico se muestra por defecto en base a la tasa de ahorro promedio real del usuario. Con el botón "🎯 Simular tasa" se despliega un panel donde se puede ingresar una tasa de ahorro hipotética (0–100%) y ver al instante cómo quedaría proyectado el balance de los próximos meses con esa tasa, sin perder la vista original ("Volver al promedio").
- Tabla de detalle mensual (real y proyectado).
- **Últimas transacciones cargadas**: muestra las transacciones en el orden en que el usuario las registró (no por la fecha de la transacción), para que pueda recordar fácilmente si ya cargó algo, incluso si programó pagos o cobros recurrentes a futuro.
- Vista responsive optimizada para mobile.

### 💳 Transacciones
- Carga de ingresos y gastos por formulario.
- Pagos recurrentes (se programan automáticamente en meses futuros).
- Recordatorios configurables (24 hs antes de la fecha).
- Categorización por rubro (Alimentación, Alquiler, Servicios, Transporte, Salud, Educación, Entretenimiento, Ropa, Tecnología, Sueldo, Freelance, Inversiones, etc.).
- Tabla con filtrado, ordenamiento y eliminación de filas.

### 🎙️ Carga de transacciones por voz
- Pestaña dedicada donde se graba un audio describiendo la transacción ("Gasté 1500 en el supermercado hoy").
- El audio se transcribe con **Whisper (Groq)** y se interpreta con un modelo de lenguaje (Groq) para completar automáticamente tipo, monto, categoría, descripción y fecha, quedando listo para confirmar y guardar.
- Misma funcionalidad disponible desde el **bot de Telegram** (texto libre o mensaje de voz).

### 🤖 Bot de Telegram (`bot.py`)
- Vinculación con usuario y contraseña de la app.
- Carga de transacciones por texto libre o por mensaje de voz.
- Corre en un hilo en paralelo al servidor web (se inicia automáticamente junto con `app.py`).

### 🚨 Alertas
- Recordatorios de transacciones próximas a vencer.
- Alertas de liquidez automáticas (mes actual + próximos 4 meses): niveles de "Precaución", "Atención", "Crítico" y "Grave" según qué porcentaje de los ingresos representan los gastos, o si hay gastos sin ingresos registrados.
- Consejos generales para mejorar la liquidez.

### 📈 Recomendaciones de Inversión
- Basadas en el capital disponible (balance acumulado), con 4 niveles de capital y recomendaciones específicas para el contexto argentino (cajas de ahorro remuneradas, plazos fijos, FCI, LECAP/BONCAP, CEDEARs, cauciones, etc.).

### 🧠 Test de Perfil de Inversor
Cuestionario de **13 preguntas** distribuidas en 4 dimensiones que suman un puntaje total de **100 puntos**:

| Dimensión | Peso | Preguntas |
|---|---|---|
| A — Situación Financiera | 25 pts | 5 de opción múltiple |
| B — Horizonte y Objetivos | 15 pts | 2 de opción múltiple |
| C — Conocimiento Financiero | 25 pts | 1 de opción múltiple + **2 abiertas evaluadas por IA** (conocimiento real y experiencia previa invirtiendo) |
| D — Tolerancia Psicológica al Riesgo | 35 pts | 1 de opción múltiple + **2 abiertas evaluadas por IA** (actitud ante la incertidumbre y efecto FOMO) |

- Las **preguntas abiertas** se pueden responder escribiendo o **grabando un audio** (se transcribe automáticamente con Groq Whisper y se vuelca al campo de texto).
- Cada respuesta abierta es evaluada por un modelo de lenguaje (Groq `openai/gpt-oss-120b`) que asigna un puntaje según criterios definidos por pregunta, con una breve explicación visible para el usuario.
- Mecanismo de **"auto-conservador"**: ciertas respuestas (p. ej. pánico ante una caída del mercado, o mostrar disposición a invertir todo el capital sin entender el riesgo ante un efecto FOMO) fuerzan directamente el perfil **Conservador**, sin importar el puntaje acumulado en el resto del test.
- 5 perfiles resultantes (Conservador, Conservador Moderado, Moderado, Moderado Agresivo, Agresivo), cada uno con asignación de cartera sugerida y activos recomendados.
- El usuario puede rehacer el test cuando quiera; el resultado se guarda en Supabase y se muestra por defecto la próxima vez que entra a la pestaña.

### 📋 Reporte Mensual con IA
- Selección del mes a analizar (desplegable con los últimos 12 meses).
- Genera un informe narrativo en español (Groq) con: resumen ejecutivo, evolución del ahorro, análisis por rubro, alertas del próximo mes, recomendaciones de inversión y consejo del mes.
- KPIs del mes seleccionado (Ingresos, Gastos, Balance, Tasa de ahorro vs. mes anterior).
- **Descarga en Excel (.xlsx)** con dos hojas:
  1. **Tus gastos del mes**: detalle de transacciones del mes con totales.
  2. **Resumen general**: KPIs, gastos por categoría (mes actual vs. anterior), gastos programados del próximo mes e informe generado por IA.
  Las columnas de montos vienen con el ancho ya ajustado para que los números se vean completos al abrir el archivo.

---

## Modelos de IA utilizados (Groq)

La app usa el modelo **`openai/gpt-oss-120b`** de Groq para todas las tareas de generación/evaluación de texto (extracción de transacciones, evaluación de preguntas abiertas del test de inversor y generación del reporte mensual), y **`whisper-large-v3`** para transcripción de audio. Al ser un modelo de razonamiento, las llamadas usan `reasoning_effort="low"` y un `max_tokens` con margen suficiente para que el razonamiento interno del modelo no consuma todo el presupuesto de tokens antes de emitir la respuesta final.

> Si Groq deprecara el modelo actual en el futuro, alcanza con actualizar el string del modelo en `groq_utils.py` e `investor_profile.py`.

---

## Base de datos

La app usa **PostgreSQL (Supabase)** con las siguientes tablas principales:
- `users`: usuarios, contraseña hasheada, pregunta/respuesta de seguridad.
- `categories`: categorías de ingresos y gastos por usuario.
- `transactions`: todas las transacciones registradas (incluye recurrencia y recordatorios).
- `investor_profiles`: resultado guardado del test de perfil de inversor por usuario.

---

## Despliegue

Incluye `Procfile.txt` (`web: python app.py`) para plataformas tipo Render/Heroku. La app toma el puerto de la variable de entorno `PORT` (por defecto 8050 en local).

---

## Dependencias

| Paquete | Uso |
|---|---|
| dash | Framework web interactivo |
| dash-bootstrap-components | Componentes UI (Bootstrap) |
| plotly | Gráficos interactivos |
| pandas | Procesamiento de datos |
| psycopg2-binary | Conexión a PostgreSQL |
| python-dotenv | Carga de variables de entorno |
| bcrypt | Hasheo de contraseñas |
| groq | Transcripción de audio y generación/evaluación de texto con IA |
| openpyxl | Generación del reporte mensual en Excel |
| python-telegram-bot | Bot de Telegram para carga de transacciones |