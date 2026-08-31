"""
investor_profile.py — Cuestionario de perfil de inversor.
Lógica de preguntas, puntuación, evaluación IA (preguntas de texto libre)
y persistencia en Supabase.
"""

import json
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
    # ── A — Situación Financiera (25 pts) ──────────────────
    {
        "id":    "q1_1",
        "dim":   "A — Situación Financiera",
        "text":  "¿Cuál es tu situación laboral actual?",
        "type":  "single",
        "options": [
            (0, "Desempleado o con trabajos esporádicos/ocasionales"),
            (1, "Trabajo independiente o freelance con ingresos variables"),
            (3, "Relación de dependencia o trabajo independiente con ingresos regulares y estables"),
            (5, "Profesional con alta estabilidad y trayectoria"),
        ],
    },
    {
        "id":    "q1_2",
        "dim":   "A — Situación Financiera",
        "text":  "¿Cuál es tu nivel de estudios?",
        "type":  "single",
        "options": [
            (0, "Secundario completo o incompleto / Terciario o universitario en curso"),
            (2, "Terciario o Universitario completo en áreas NO relacionadas con finanzas o economía"),
            (5, "Terciario, Universitario o Posgrado con formación directa en Economía, Finanzas, Administración o carreras afines"),
        ],
    },
    {
        "id":    "q2",
        "dim":   "A — Situación Financiera",
        "text":  "¿Cuál es el nivel y estabilidad de tus ingresos?",
        "type":  "single",
        "options": [
            (1, "Variables / Inestables (trabajos esporádicos o estacionales)"),
            (2, "Estables, pero cubren lo justo para mis gastos básicos mensuales"),
            (4, "Estables, con capacidad de ahorro regular (hasta un 20% de mi ingreso)"),
            (7, "Altos y muy estables, con alta capacidad de ahorro (más del 20%)"),
        ],
    },
    {
        "id":    "q3",
        "dim":   "A — Situación Financiera",
        "text":  "¿Tenés personas a cargo?",
        "type":  "single",
        "options": [
            (1, "Soy el único sostén de una familia numerosa (3 o más personas a cargo)"),
            (2, "Tengo familia a cargo, pero comparto los gastos con mi pareja / otro familiar"),
            (4, "No tengo personas a cargo / Mis ingresos son 100% para mí"),
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
            (0, "Necesito usar este dinero para pagar deudas o gastos fijos el próximo mes"),
            (1, "Podría necesitar una parte importante de estos fondos en los próximos 6 a 12 meses"),
            (3, "No tengo gastos grandes previstos a corto plazo, pero me gusta tener liquidez"),
            (4, "No planeo tocar este dinero, mis gastos cotidianos y emergencias ya están cubiertos"),
        ],
    },
    # ── B — Horizonte y Objetivos (15 pts) ─────────────────
    {
        "id":    "q5",
        "dim":   "B — Horizonte y Objetivos",
        "text":  "¿En qué plazo pensás retirar tu inversión?",
        "type":  "single",
        "options": [
            (0, "Menos de 1 año (Corto plazo)"),
            (2, "Entre 1 y 3 años (Mediano plazo)"),
            (5, "Entre 3 y 5 años (Mediano-Largo plazo)"),
            (7, "Más de 5 años (Largo plazo)"),
        ],
    },
    {
        "id":    "q6",
        "dim":   "B — Horizonte y Objetivos",
        "text":  "¿Cuál es el objetivo principal de esta inversión?",
        "type":  "single",
        "auto_conservador": True,
        "auto_value": 1,
        "options": [
            (1, "Proteger el valor de mis ahorros sin perder dinero, aunque gane poco"),
            (3, "Ganar un poco más que la inflación, asumiendo un riesgo mínimo"),
            (6, "Lograr un crecimiento significativo a mediano plazo, aceptando fluctuaciones moderadas"),
            (8, "Maximizar mis ganancias a largo plazo, asumiendo grandes riesgos y volatilidad"),
        ],
    },
    # ── C — Conocimiento Financiero (25 pts) ───────────────
    {
        "id":    "q7",
        "dim":   "C — Conocimiento Financiero",
        "text":  "¿Cuál es tu experiencia con instrumentos financieros?",
        "type":  "single",
        "options": [
            (2, "Ninguna. Solo conozco cuentas de ahorro, billeteras virtuales o plazos fijos"),
            (4, "Básica. Entiendo cómo funcionan bonos y FCI de bajo riesgo"),
            (6, "Intermedia. Conozco y he operado acciones, CEDEARs o bonos corporativos"),
            (8, "Avanzada. Entiendo y opero opciones, futuros, ETFs volátiles y/o criptomonedas"),
        ],
    },
    {
        "id":   "q10",
        "dim":  "C — Conocimiento Financiero",
        "text": (
            "Si tuvieras que explicarle a un nene de 10 años cuál es la diferencia entre ahorrar e "
            "invertir, ¿qué ejemplo usarías?"
        ),
        "type":        "text",
        "short_label": "Conocimiento real",
        "max_score":   8,
        "criteria": (
            "- 0 a 2 puntos: Nivel bajo. Da ejemplos confusos o asocia invertir únicamente a dejar el "
            "dinero en el banco sin comprender el riesgo o el rendimiento.\n"
            "- 3 a 5 puntos: Nivel medio. Entiende la idea de rendimiento básico y la diferencia entre "
            "guardar y generar un interés.\n"
            "- 6 a 8 puntos: Nivel alto. Comprende conceptualmente el riesgo, el costo de oportunidad "
            "y la multiplicación del capital a través del tiempo."
        ),
    },
    {
        "id":   "q12",
        "dim":  "C — Conocimiento Financiero",
        "text": (
            "Contanos de tus experiencias previas invirtiendo (en qué lo hiciste, cómo te fue, alguna "
            "anécdota, etc.)."
        ),
        "type":        "text",
        "short_label": "Experiencia previa invirtiendo",
        "max_score":   9,
        "criteria": (
            "- 0 a 3 puntos: Sin experiencia previa invirtiendo, o la relata de forma confusa/vaga, sin "
            "poder mencionar en qué invirtió ni qué aprendió.\n"
            "- 4 a 6 puntos: Tiene experiencia limitada, en instrumentos simples y de bajo riesgo (ej. "
            "plazo fijo, compra de dólares), o el relato no evidencia una comprensión clara de riesgos "
            "ni resultados.\n"
            "- 7 a 9 puntos: Tiene experiencia relevante y demuestra conocimiento real: menciona "
            "instrumentos concretos (acciones, bonos, CEDEARs, criptomonedas, fondos, etc.), resultados "
            "obtenidos y aprendizajes o gestión del riesgo."
        ),
    },
    # ── D — Tolerancia Psicológica al Riesgo (35 pts) ──────
    {
        "id":    "q8",
        "dim":   "D — Tolerancia Psicológica al Riesgo",
        "text":  "Imaginá que invertís $1.000.000 y al mes tu saldo cae a $700.000 (−30%). ¿Qué hacés?",
        "type":  "single",
        "auto_conservador": True,
        "auto_value": 0,
        "options": [
            (0,  "Entro en pánico y vendo todo inmediatamente para no seguir perdiendo"),
            (3,  "Vendo una parte para proteger lo que queda"),
            (8,  "No hago nada, espero a que el mercado se recupere confiando en el largo plazo"),
            (12, "Aprovecho la caída para comprar más, ya que los activos están más baratos"),
        ],
    },
    {
        "id":   "q9",
        "dim":  "D — Tolerancia Psicológica al Riesgo",
        "text": (
            "Si te ofrecen una inversión que tiene un 50% de probabilidad de duplicar tu dinero "
            "y un 50% de probabilidad de perder la mitad, ¿la tomarías? Contanos por qué."
        ),
        "type":        "text",
        "short_label": "Actitud ante la incertidumbre",
        "max_score":   13,
        "criteria": (
            "- 0 a 3 puntos: Rechazo total al riesgo, prioriza la seguridad absoluta.\n"
            "- 4 a 7 puntos: Duda, la tomaría solo con una pequeña parte de su capital.\n"
            "- 8 a 13 puntos: Aceptación total, entiende la asimetría riesgo/beneficio y le entusiasma."
        ),
    },
    {
        "id":   "q11",
        "dim":  "D — Tolerancia Psicológica al Riesgo",
        "text": (
            "Un conocido te muestra que ganó mucha plata en pocos días con una criptomoneda nueva de la "
            "que nunca escuchaste hablar, y te insiste para que inviertas hoy mismo. ¿Qué hacés?"
        ),
        "type":                   "text",
        "short_label":            "Efecto FOMO",
        "max_score":              10,
        "detect_auto_conservador": True,
        "criteria": (
            "- 0 a 4 puntos (Rechazo total): descarta la oportunidad de plano, prioriza la seguridad de "
            "su capital y rechaza invertir en instrumentos desconocidos o esquemas de dinero fácil.\n"
            "- 5 a 7 puntos (Curiosidad cautelosa): muestra curiosidad, pero prioriza investigar a fondo "
            "antes de arriesgar dinero, o invertiría una cantidad mínima e irrelevante.\n"
            "- 8 a 10 puntos (Especulación consciente): está dispuesto a aprovechar la oportunidad, pero "
            "demuestra gestión del riesgo (ej. destinando un porcentaje menor de su cartera asumiendo que "
            "puede perderlo todo)."
        ),
    },
]

# ──────────────────────────────────────────────
# Evaluación IA — preguntas de texto libre
# ──────────────────────────────────────────────

def evaluate_open_answer(question: dict, answer_text: str) -> tuple:
    """
    Usa Groq (openai/gpt-oss-120b) para evaluar una respuesta de texto libre
    de cualquiera de las preguntas abiertas del cuestionario.

    Devuelve (score: int, explanation: str, auto_conservador: bool)
    """
    max_score = question.get("max_score", 10)
    fallback_score = max_score // 2

    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or api_key == "YOUR_GROQ_API_KEY_HERE":
            return fallback_score, "Evaluación manual no disponible (sin API key).", False

        client = Groq(api_key=api_key)

        auto_instruction = ""
        if question.get("detect_auto_conservador"):
            auto_instruction = (
                "\n\nADEMÁS: Si la respuesta indica que el usuario invertiría la totalidad o gran parte "
                "de su capital de forma apresurada persiguiendo un rendimiento explosivo, sin comprender "
                "el riesgo que asume, marcá \"auto_conservador\": true (esto indica desconocimiento del "
                "riesgo y fuerza perfil Conservador). En cualquier otro caso, marcá \"auto_conservador\": false."
            )

        prompt = f"""Sos un evaluador de perfiles de inversión. Analizá la siguiente respuesta a una pregunta abierta y asignale un puntaje según los criterios.

Pregunta: "{question['text']}"
Respuesta del usuario: "{answer_text}"

Criterios de puntuación (máximo {max_score} puntos):
{question.get('criteria', '')}{auto_instruction}

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:
{{"score": 0, "explanation": "breve explicación de 1 oración del porqué del puntaje", "auto_conservador": false}}"""

        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
            reasoning_effort="low",
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        if not raw:
            return fallback_score, "Evaluación IA no disponible (respuesta vacía del modelo).", False

        data  = json.loads(raw)
        score = max(0, min(max_score, int(data.get("score", fallback_score))))
        expl  = data.get("explanation", "")
        auto  = bool(data.get("auto_conservador", False)) if question.get("detect_auto_conservador") else False
        return score, expl, auto
    except Exception as e:
        return fallback_score, f"Error en evaluación IA: {str(e)}", False


# ──────────────────────────────────────────────
# Cálculo de perfil
# ──────────────────────────────────────────────

def calculate_profile(answers: dict) -> dict:
    """
    answers: {question_id: value}
      - Para preguntas de opción múltiple: value = puntaje (int)
      - Para preguntas de texto libre (q9, q10, q11): value = texto libre (str)

    Devuelve dict con score, profile_name, profile_data, auto_conservador, text_evaluations
    """
    total            = 0
    auto_cons        = False
    text_evaluations = []  # [{id, label, score, max_score, explanation}, ...]

    for q in QUESTIONS:
        qid = q["id"]
        if qid not in answers:
            continue

        if q["type"] == "text":
            score, expl, ai_auto = evaluate_open_answer(q, str(answers[qid]))
            total += score
            text_evaluations.append({
                "id":         qid,
                "label":      q.get("short_label", q["text"][:40]),
                "score":      score,
                "max_score":  q.get("max_score", 10),
                "explanation": expl,
            })
            if ai_auto:
                auto_cons = True
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
        "score":            total,
        "profile_name":     profile["name"],
        "profile":          profile,
        "auto_conservador": auto_cons,
        "text_evaluations": text_evaluations,
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