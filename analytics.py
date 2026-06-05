"""
analytics.py — KPIs, alertas de liquidez, recordatorios, proyecciones y recomendaciones.
"""

import pandas as pd
from datetime import datetime, timedelta
from database import get_balance_up_to, get_pending_reminders, get_conn


# ──────────────────────────────────────────────
# KPIs del mes
# ──────────────────────────────────────────────

def get_monthly_kpis(user_id: int, year_month: str = None) -> dict:
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT type, COALESCE(SUM(amount),0) FROM transactions "
        "WHERE user_id=%s AND TO_CHAR(date,'YYYY-MM')=%s GROUP BY type",
        (user_id, year_month))
    r = dict(c.fetchall())
    conn.close()
    inc = float(r.get("income", 0)); exp = float(r.get("expense", 0))
    bal = inc - exp
    return {"income": inc, "expense": exp, "balance": bal,
            "savings_rate": bal / inc * 100 if inc > 0 else 0.0}


def get_current_balance(user_id: int) -> float:
    return get_balance_up_to(user_id, datetime.now().strftime("%Y-%m-%d"))


# ──────────────────────────────────────────────
# Proyección del flujo de fondos
# ──────────────────────────────────────────────

def get_cash_flow_projection(user_id: int, months_back: int = 2, months_ahead: int = 5) -> list:
    today = datetime.now()
    tmp_m = today.month - months_back; tmp_y = today.year
    while tmp_m < 1: tmp_m += 12; tmp_y -= 1
    seed  = datetime(tmp_y, tmp_m, 1) - timedelta(days=1)
    running = get_balance_up_to(user_id, seed.strftime("%Y-%m-%d"))
    conn = get_conn(); projections = []

    for i in range(months_back + months_ahead + 1):
        offset = i - months_back
        m = today.month + offset; y = today.year
        while m > 12: m -= 12; y += 1
        while m < 1:  m += 12; y -= 1
        ym = f"{y}-{m:02d}"
        c = conn.cursor()
        c.execute("SELECT type, COALESCE(SUM(amount),0) FROM transactions "
                  "WHERE user_id=%s AND TO_CHAR(date,'YYYY-MM')=%s GROUP BY type",
                  (user_id, ym))
        res = dict(c.fetchall())
        inc = float(res.get("income", 0)); exp = float(res.get("expense", 0))
        running += inc - exp
        projections.append({"month": ym, "income": inc, "expense": exp,
                             "net": inc - exp, "balance": running, "is_future": offset > 0})
    conn.close()
    return projections


# ──────────────────────────────────────────────
# Alertas de liquidez
# ──────────────────────────────────────────────

def get_liquidity_alerts(user_id: int, months_ahead: int = 4) -> list:
    today   = datetime.now()
    balance = get_current_balance(user_id)
    alerts  = []; running = balance
    conn    = get_conn()

    for i in range(1, months_ahead + 1):
        m = today.month + i; y = today.year
        while m > 12: m -= 12; y += 1
        ym = f"{y}-{m:02d}"
        c = conn.cursor()
        c.execute("SELECT type, COALESCE(SUM(amount),0) FROM transactions "
                  "WHERE user_id=%s AND TO_CHAR(date,'YYYY-MM')=%s GROUP BY type",
                  (user_id, ym))
        res = dict(c.fetchall())
        inc = float(res.get("income", 0)); exp = float(res.get("expense", 0))
        running += inc - exp
        if exp == 0 and inc == 0: continue
        deficit = exp - inc
        if running < 0:
            alerts.append({"month": ym, "severity": "danger",
                "message": f"🔴 CRÍTICO — {ym}: gastos superan ingresos en ${deficit:,.2f}. Balance proyectado NEGATIVO: ${running:,.2f}."})
        elif deficit > 0:
            alerts.append({"month": ym, "severity": "warning",
                "message": f"🟡 ATENCIÓN — {ym}: los gastos superarán los ingresos en ${deficit:,.2f}. Balance: ${running:,.2f}."})
        elif running < balance * 0.15 and balance > 0:
            alerts.append({"month": ym, "severity": "warning",
                "message": f"🟠 PRECAUCIÓN — {ym}: balance podría caer a ${running:,.2f}, menos del 15 % del actual."})
    conn.close()
    return alerts


# ──────────────────────────────────────────────
# Alertas de recordatorios
# ──────────────────────────────────────────────

def get_reminder_alerts(user_id: int) -> list:
    reminders = get_pending_reminders(user_id)
    alerts = []
    for desc, amount, date, category, tx_type in reminders:
        label = "Ingreso" if tx_type == "income" else "Gasto"
        alerts.append({
            "severity": "info",
            "message": f"🔔 RECORDATORIO — {label} de ${float(amount):,.2f} ({category}: {desc}) programado para el {date}."
        })
    return alerts


# ──────────────────────────────────────────────
# Recomendaciones de inversión
# ──────────────────────────────────────────────

def get_investment_recommendations(surplus: float) -> list:
    if surplus <= 0:
        return [{"icon": "❌", "title": "Sin capital excedente",
                 "description": "No hay saldo disponible. Revisá tus gastos o buscá fuentes adicionales.", "risk": "—"}]
    if surplus < 50_000:
        return [
            {"icon": "🏦", "title": "Caja de Ahorro Remunerada",
             "description": f"Con ${surplus:,.2f} la caja de ahorro es la opción más segura y líquida. Rinde ~70-80 % TNA.", "risk": "Muy Bajo"},
            {"icon": "📈", "title": "Plazo Fijo UVA",
             "description": "Protege tus ahorros de la inflación. Mínimo $10.000, plazo 90 días.", "risk": "Bajo"},
        ]
    if surplus < 200_000:
        return [
            {"icon": "🏦", "title": "Plazo Fijo Tradicional",
             "description": f"Con ${surplus:,.2f} obtenés ~70-80 % TNA a 30 días con capital garantizado.", "risk": "Muy Bajo"},
            {"icon": "💰", "title": "FCI Money Market",
             "description": "Fondo de liquidez inmediata con rescate en 24 h.", "risk": "Bajo"},
            {"icon": "📊", "title": "Plazo Fijo UVA",
             "description": "Cobertura de inflación con rendimiento real positivo.", "risk": "Bajo"},
        ]
    if surplus < 1_000_000:
        return [
            {"icon": "📈", "title": "FCI Renta Fija", "description": f"Con ${surplus:,.2f} accedés a fondos diversificados.", "risk": "Bajo–Medio"},
            {"icon": "💹", "title": "Cauciones Bursátiles", "description": "Préstamos a corto plazo en el mercado de capitales.", "risk": "Bajo"},
            {"icon": "🏛️", "title": "LECAP / BONCAP", "description": "Letras y bonos del Tesoro con tasas fijas atractivas.", "risk": "Medio"},
            {"icon": "🌎", "title": "CEDEARs", "description": "Empresas internacionales desde Argentina. Cobertura cambiaria implícita.", "risk": "Medio–Alto"},
        ]
    return [
        {"icon": "🎯", "title": "Cartera Diversificada",
         "description": f"Con ${surplus:,.2f}: 40 % renta fija, 30 % CEDEARs, 20 % acciones locales, 10 % alternativos.", "risk": "Diversificado"},
        {"icon": "📊", "title": "Acciones (MERVAL)", "description": "Empresas líderes argentinas.", "risk": "Alto"},
        {"icon": "💵", "title": "Bonos en USD", "description": "Cobertura cambiaria con bonos dolarizados.", "risk": "Medio–Alto"},
        {"icon": "🏠", "title": "Crowdfunding Inmobiliario", "description": "Real Estate a través de plataformas digitales.", "risk": "Medio"},
        {"icon": "💹", "title": "FCI Renta Variable", "description": "Fondos con exposición a renta variable diversificada.", "risk": "Alto"},
    ]
