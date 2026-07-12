"""
investor_profile.py — Cuestionario de perfil de inversor.
Lógica de preguntas, puntuación, evaluación IA (pregunta 9)
y persistencia en Supabase.
"""

import os
from database import get_conn
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Definición de perfiles
# ──────────────────────────────────────────────

PROFILES = [
    {
        "name":  "Conservador",
        "range": (0, 25),
        "color": "#3B9EFF",
        "icon":  "🛡️",
        "alloc": "100% Renta Fija de muy corto plazo.",
        "assets": [
            "Cauciones bursátiles (1, 7 o 14 días)",
            "FCI Money Market",
            "Plazos fijos tradicionales",
            "Letras de Tesoro (LECAP)",
        ],
    },
    {
        "name":  "Conservador Moderado",
        "range": (26, 45),
        "color": "#00D4AA",
        "icon":  "🔵",
        "alloc": "80% Renta Fija / 20% Renta Variable.",
        "assets": [
            "RF (80%): ONs sector energético/telecomunicaciones",
            "RF (80%): Bonos soberanos de corto plazo",
            "RV (20%): CEDEARs de empresas maduras con dividendos (Coca-Cola, J&J, Walmart)",
        ],
    },
    {
        "name":  "Moderado",
        "range": (46, 65),
        "color": "#FFB84D",
        "icon":  "⚖️",
        "alloc": "50% Renta Fija / 50% Renta Variable.",
        "assets": [
            "RF (50%): ONs diversificadas y FCI Renta Fija",
            "RV (50%): S&P 500 vía CEDEARs",
            "RV (50%): CEDEARs tecnológicos consolidados (Apple, Microsoft)",
        ],
    },
    {
        "name":  "Moderado Agresivo",
        "range": (66, 85),
        "color": "#FF8C00",
        "icon":  "📈",
        "alloc": "20% Renta Fija / 80% Renta Variable.",
        "assets": [
            "RV (80%): ETFs tecnológicos (QQQ)",
            "RV (80%): Acciones de mercados emergentes",
            "RV (80%): CEDEARs de empresas de alto crecimiento",
            "RF (20%): ONs en dólares como amortiguador",
        ],
    },
    {
        "name":  "Agresivo",
        "range": (86, 100),
        "color": "#FF5C5C",
        "icon":  "🚀",
        "alloc": "100% Renta Variable y Activos Alternativos.",
        "assets": [
            "Acciones de alto riesgo y empresas disruptivas",
            "Criptomonedas (Bitcoin, Ethereum, altcoins)",
            "Instrumentos derivados (opciones y futuros)",
            "Startups y biotecnología",
        ],
    },
]

# ──────────────────────────────────────────────
# Preguntas
# ──────────────────────────────────────────────

QUESTIONS = [
    {
        "id":    "q1_1",
        "dim":   "A — Situación Financiera",
        "text":  "¿Cuál es tu situación laboral actual?",
        "type":  "single",
        "options": [
            (0,  "Desempleado o con trabajos esporádicos/ocasionales"),
            (1,  "Trabajo independiente o freelance con ingresos variables"),
            (2,  "Relación de dependencia o trabajo independiente con ingresos regulares y estables"),
            (3,  "Profesional con alta estabilidad y trayectoria"),
        ],
    },
    {
        "id":    "q1_2",
        "dim":   "A — Situación Financiera",
        "text":  "¿Cuál es tu nivel de estudios?",
        "type":  "single",
        "options": [
            (0, "Secundario completo o incompleto / Terciario o universitario en curso"),
            (1, "Terciario o Universitario completo en áreas NO relacionadas con finanzas"),
            (3, "Terciario, Universitario o Posgrado en Economía, Finanzas, Administración o afines"),
        ],
    },
    {
        "id":    "q2",
        "dim":   "A — Situación Financiera",
        "text":  "¿Cuál es el nivel y estabilidad de tus ingresos?",
        "type":  "single",
        "options": [
            (1,  "Variables / Inestables (trabajos esporádicos o estacionales)"),
            (3,  "Estables, pero cubren lo justo para mis gastos básicos mensuales"),
            (7,  "Estables, con capacidad de ahorro regular (hasta un 20% de mi ingreso)"),
            (12, "Altos y muy estables, con alta capacidad de ahorro (más del 20%)"),
        ],
    },
    {
        "id":    "q3",
        "dim":   "A — Situación Financiera",
        "text":  "¿Tenés personas a cargo?",
        "type":  "single",
        "options": [
            (1, "Soy el único sostén de una familia numerosa (3 o más personas a cargo)"),
            (3, "Tengo familia a cargo, pero comparto los gastos con mi pareja / otro familiar"),
            (5, "No tengo personas a cargo / Mis ingresos son 100% para mí"),
        ],
    },
    {
        "id":    "q4",
        "dim":   "A — Situación Financiera",
        "text":  "¿Tenés gastos importantes previstos a corto plazo?",
        "type":  "single",
        "auto_conservador": True,
        "auto_value": 0,
        "options": [
            (0,  "Necesito usar este dinero para pagar deudas o gastos fijos el próximo mes"),
            (3,  "Podría necesitar una parte importante de estos fondos en los próximos 6 a 12 meses"),
            (7,  "No tengo gastos grandes previstos a corto plazo, pero me gusta tener liquidez"),
            (11, "No planeo tocar este dinero, mis gastos cotidianos y emergencias ya están cubiertos"),
        ],
    },
    {
        "id":    "q5",
        "dim":   "B — Horizonte y Objetivos",
        "text":  "¿En qué plazo pensás retirar tu inversión?",
        "type":  "single",
        "options": [
            (2,  "Menos de 1 año (Corto plazo)"),
            (4,  "Entre 1 y 3 años (Mediano plazo)"),
            (7,  "Entre 3 y 5 años (Mediano-Largo plazo)"),
            (11, "Más de 5 años (Largo plazo)"),
        ],
    },
    {
        "id":    "q6",
        "dim":   "B — Horizonte y Objetivos",
        "text":  "¿Cuál es el objetivo principal de esta inversión?",
        "type":  "single",
        "auto_conservador": True,
        "auto_value": 2,
        "options": [
            (2,  "Proteger el valor de mis ahorros sin perder dinero, aunque gane poco"),
            (5,  "Ganar un poco más que la inflación, asumiendo un riesgo mínimo"),
            (8,  "Lograr un crecimiento significativo a mediano plazo, aceptando fluctuaciones moderadas"),
            (10, "Maximizar mis ganancias a largo plazo, asumiendo grandes riesgos y volatilidad"),
        ],
    },
    {
        "id":    "q7",
        "dim":   "C — Conocimiento Financiero",
        "text":  "¿Cuál es tu experiencia con instrumentos financieros?",
        "type":  "single",
        "options": [
            (3,  "Ninguna. Solo conozco cuentas de ahorro, billeteras virtuales o plazos fijos"),
            (7,  "Básica. Entiendo cómo funcionan bonos y FCI de bajo riesgo"),
            (11, "Intermedia. Conozco y he operado acciones, CEDEARs o bonos corporativos"),
            (15, "Avanzada. Entiendo y opero opciones, futuros, ETFs volátiles y/o criptomonedas"),
        ],
    },
    {
        "id":    "q8",
        "dim":   "D — Tolerancia Psicológica al Riesgo",
        "text":  "Imaginá que invertís $1.000.000 y al mes tu saldo cae a $700.000 (−30%). ¿Qué hacés?",
        "type":  "single",
        "auto_conservador": True,
        "auto_value": 0,
        "options": [
            (0,  "Entro en pánico y vendo todo inmediatamente para no seguir perdiendo"),
            (4,  "Vendo una parte para proteger lo que queda"),
            (10, "No hago nada, espero a que el mercado se recupere confiando en el largo plazo"),
            (15, "Aprovecho la caída para comprar más, ya que los activos están más baratos"),
        ],
    },
    {
        "id":   "q9",
        "dim":  "D — Tolerancia Psicológica al Riesgo",
        "text": (
            "Si te ofrecen una inversión que tiene un 50% de probabilidad de duplicar tu dinero "
            "y un 50% de probabilidad de perder la mitad, ¿la tomarías? Contanos por qué."
        ),
        "type": "text",
    },
]

# ──────────────────────────────────────────────
# Evaluación IA — pregunta 9
# ──────────────────────────────────────────────

def evaluate_q9_with_ai(answer_text: str) -> tuple:
    """
    Usa Groq LLaMA para evaluar la respuesta de texto libre de la pregunta 9.
    Devuelve (score: int, explanation: str)
    """
    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or api_key == "YOUR_GROQ_API_KEY_HERE":
            # Fallback: puntaje medio si no hay API
            return 7, "Evaluación manual no disponible (sin API key)."

        client = Groq(api_key=api_key)
        prompt = f"""Sos un evaluador de perfiles de inversión. Analizá la siguiente respuesta y asignale un puntaje del 0 al 15 según la actitud hacia el riesgo financiero.

Respuesta del usuario: "{answer_text}"

Criterios de puntuación:
- 0 a 4 puntos: Rechazo total al riesgo. El usuario prioriza la seguridad absoluta, no tomaría ningún riesgo.
- 5 a 10 puntos: Actitud moderada. Dudaría, la tomaría solo con una pequeña parte de su capital.
- 11 a 15 puntos: Aceptación total del riesgo. Entiende la asimetría riesgo/beneficio y le entusiasma.

Respondé ÚNICAMENTE con JSON válido sin texto adicional:
{{"score": 7, "explanation": "breve explicación de 1 oración del porqué del puntaje"}}"""

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
        )
        import json
        raw  = resp.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        score = max(0, min(15, int(data.get("score", 7))))
        expl  = data.get("explanation", "")
        return score, expl
    except Exception as e:
        return 7, f"Error en evaluación IA: {str(e)}"


# ──────────────────────────────────────────────
# Cálculo de perfil
# ──────────────────────────────────────────────

def calculate_profile(answers: dict) -> dict:
    """
    answers: {question_id: value}
      - Para preguntas de opción múltiple: value = puntaje (int)
      - Para q9 (texto): value = texto libre (str)

    Devuelve dict con score, profile_name, profile_data, auto_conservador, q9_score, q9_explanation
    """
    total       = 0
    auto_cons   = False
    q9_score    = 0
    q9_expl     = ""

    for q in QUESTIONS:
        qid = q["id"]
        if qid not in answers:
            continue

        if q["type"] == "text":
            q9_score, q9_expl = evaluate_q9_with_ai(str(answers[qid]))
            total += q9_score
        else:
            val = int(answers[qid])
            total += val
            # Detectar respuestas que fuerzan perfil conservador
            if q.get("auto_conservador") and val == q.get("auto_value", 0):
                auto_cons = True

    # Si hay trigger conservador, el puntaje máximo es 25
    if auto_cons:
        total = min(total, 25)

    # Determinar perfil
    profile = PROFILES[0]
    for p in PROFILES:
        lo, hi = p["range"]
        if lo <= total <= hi:
            profile = p
            break
    # Si supera 100, agresivo
    if total > 100:
        profile = PROFILES[-1]

    return {
        "score":           total,
        "profile_name":    profile["name"],
        "profile":         profile,
        "auto_conservador":auto_cons,
        "q9_score":        q9_score,
        "q9_explanation":  q9_expl,
    }


# ──────────────────────────────────────────────
# Persistencia en Supabase
# ──────────────────────────────────────────────

def init_profile_table():
    """Crea la tabla investor_profiles si no existe."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS investor_profiles (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            score        INTEGER NOT NULL,
            profile_name TEXT    NOT NULL,
            completed_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    conn.close()

def get_investor_profile(user_id: int) -> dict | None:
    """Devuelve el perfil guardado del usuario o None si no completó el cuestionario."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT score, profile_name, completed_at FROM investor_profiles WHERE user_id = %s",
        (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    score, profile_name, completed_at = row
    profile = next((p for p in PROFILES if p["name"] == profile_name), PROFILES[0])
    return {"score": score, "profile_name": profile_name,
            "profile": profile, "completed_at": str(completed_at)[:10]}

def save_investor_profile(user_id: int, score: int, profile_name: str) -> None:
    """Guarda o actualiza el perfil del usuario."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO investor_profiles (user_id, score, profile_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
            SET score = EXCLUDED.score,
                profile_name = EXCLUDED.profile_name,
                completed_at = NOW()
    """, (user_id, score, profile_name))
    conn.commit()
    conn.close()