"""
groq_utils.py — Integración con Groq API.
Transcripción de audio (Whisper) y generación de texto (LLaMA 3).
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")


def _client():
    if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
        raise ValueError("GROQ_API_KEY no configurada. Editá el archivo .env con tu clave de Groq.")
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


# ──────────────────────────────────────────────
# Transcripción de audio
# ──────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, fmt: str = "webm") -> str:
    """Transcribe audio bytes a texto usando Whisper en Groq."""
    client = _client()
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        with open(tmp, "rb") as af:
            resp = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=(f"audio.{fmt}", af),
                language="es",
            )
        return resp.text
    finally:
        os.unlink(tmp)


# ──────────────────────────────────────────────
# Extracción de transacción desde texto
# ──────────────────────────────────────────────

def extract_transaction(text: str, categories: list) -> dict:
    """
    Extrae datos de transacción de texto libre.
    categories: lista de (id, name, type)
    Devuelve dict {type, amount, category_id, description, date}
    """
    client = _client()
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    cat_list = "\n".join([f"  ID {c[0]}: {c[1]} ({c[2]})" for c in categories])

    prompt = f"""Extraé los datos de una transacción financiera del siguiente texto en español.

Texto: "{text}"
Fecha de hoy: {today}
Fecha de ayer: {yesterday}

Categorías disponibles:
{cat_list}

Reglas:
- "ayer" → {yesterday} | "hoy" o sin fecha → {today}
- Compra/gasto/pago → type="expense" | Cobro/ingreso/sueldo → type="income"
- Elegí la category_id más apropiada de la lista
- description: máximo 5 palabras descriptivas

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:
{{"type":"expense","amount":0.0,"category_id":1,"description":"descripción","date":"YYYY-MM-DD"}}"""

    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=600,
        reasoning_effort="low",
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    if not raw:
        raise ValueError("El modelo no devolvió contenido (respuesta vacía).")
    return json.loads(raw)


# ──────────────────────────────────────────────
# Generación del reporte mensual
# ──────────────────────────────────────────────

def generate_report(data: dict) -> str:
    """Genera un reporte mensual narrativo usando LLaMA 3 en Groq."""
    client = _client()

    cats      = "\n".join([f"  - {c[0]}: ${c[1]:,.2f}" for c in data["categories"]])      or "  Sin datos"
    prev_cats = "\n".join([f"  - {c[0]}: ${c[1]:,.2f}" for c in data["prev_categories"]]) or "  Sin datos"
    upcoming  = "\n".join([f"  - {u[0]}: ${u[1]:,.2f} el {u[2]}" for u in data["upcoming_payments"]]) or "  Sin gastos programados"

    curr_d = dict(data["categories"])
    prev_d = dict(data["prev_categories"])
    variations = []
    for cat, amt in curr_d.items():
        if cat in prev_d and prev_d[cat] > 0:
            delta = (amt - prev_d[cat]) / prev_d[cat] * 100
            variations.append(f"  - {cat}: {delta:+.1f}%")
    vars_text = "\n".join(variations) or "  Sin datos comparativos"

    prompt = f"""Sos un asesor financiero personal. Generá un reporte mensual claro y útil en español.

DATOS DEL MES {data['year_month']}:
- Ingresos: ${data['income']:,.2f}
- Gastos: ${data['expense']:,.2f}
- Balance: ${data['balance']:,.2f}
- Tasa de ahorro: {data['savings_rate']:.1f}%

MES ANTERIOR:
- Ingresos: ${data['prev_income']:,.2f}
- Gastos: ${data['prev_expense']:,.2f}
- Tasa de ahorro: {data['prev_savings_rate']:.1f}%

GASTOS POR CATEGORÍA (mes actual):
{cats}

GASTOS POR CATEGORÍA (mes anterior):
{prev_cats}

VARIACIÓN POR CATEGORÍA:
{vars_text}

GASTOS PROGRAMADOS PARA EL PRÓXIMO MES:
{upcoming}

CAPITAL DISPONIBLE PARA INVERTIR: ${data['surplus']:,.2f}

Generá el reporte con exactamente estas secciones en markdown:
## 📊 Resumen Ejecutivo
## 💰 Evolución del Ahorro
## 📈 Análisis por Rubro
## ⚠️ Alertas Próximo Mes
## 🏦 Recomendaciones de Inversión (para Argentina, específicas y concretas)
## 💡 Consejo del Mes

Usá los números reales. Sé específico y práctico. Máximo 600 palabras en total."""

    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1200,
    )
    return resp.choices[0].message.content