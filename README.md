# Finanzas Personales — App Python

Aplicación web de finanzas personales construida con **Dash + Plotly + SQLite**.

---

## Estructura

```
finanzas_personales/
├── app.py            ← Aplicación principal (UI + callbacks)
├── database.py       ← Capa de acceso a datos (SQLite)
├── analytics.py      ← KPIs, alertas, proyecciones, recomendaciones
├── requirements.txt  ← Dependencias Python
└── finanzas.db       ← Base de datos (se crea automáticamente al ejecutar)
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

# 3. Ejecutar la aplicación
python app.py
```

Acceder en el navegador: **http://localhost:8050**

---

## Funcionalidades

### 📊 Dashboard
- 4 KPI cards: Balance total, Ingresos del mes, Gastos del mes, Tasa de ahorro
- Gráfico de barras: Ingresos vs Gastos por mes
- Gráfico de torta: Gastos por rubro (mes actual)
- Gráfico de línea: Evolución del balance (real + proyectado)
- Tabla de últimas transacciones

### 💳 Transacciones
- Formulario para cargar ingresos y gastos
- Soporte para pagos recurrentes (se programan automáticamente en meses futuros)
- Categorización por rubro: Alimentación, Alquiler, Servicios, Transporte, Salud, Educación, Entretenimiento, Ropa, Tecnología, etc.
- Tabla con filtrado, ordenamiento y eliminación de filas

### 📅 Flujo de Fondos
- Gráfico combinado (barras + línea) con meses históricos y proyectados
- Tabla detallada con: Ingresos, Gastos, Neto del mes, Balance acumulado
- Los meses futuros se distinguen visualmente

### 🚨 Alertas de Liquidez
- Detección automática de meses donde los gastos superan los ingresos
- Alertas de nivel CRÍTICO (balance negativo) y ATENCIÓN (déficit mensual)
- Consejos concretos para mejorar la liquidez

### 📈 Recomendaciones de Inversión
- Basadas en el capital disponible (balance acumulado)
- 4 niveles de capital con recomendaciones específicas al contexto argentino:
  - < $50.000: Caja de ahorro remunerada, Plazo fijo UVA
  - < $200.000: Plazo fijo, FCI Money Market
  - < $1.000.000: FCI Renta fija, Cauciones, LECAP, CEDEARs
  - ≥ $1.000.000: Cartera diversificada, Acciones, Bonos en USD, Real Estate

---

## Base de datos

La app crea `finanzas.db` (SQLite) automáticamente con dos tablas:
- `categories`: categorías de ingresos y gastos
- `transactions`: todas las transacciones registradas

Para resetear los datos, simplemente eliminar el archivo `finanzas.db`.

---

## Dependencias

| Paquete                   | Uso                          |
|---------------------------|------------------------------|
| dash                      | Framework web interactivo    |
| dash-bootstrap-components | Componentes UI (Bootstrap)   |
| plotly                    | Gráficos interactivos        |
| pandas                    | Procesamiento de datos       |
