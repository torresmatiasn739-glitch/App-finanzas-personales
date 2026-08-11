"""
app.py — Aplicación principal de Finanzas Personales.
Nuevas funcionalidades: contraseña, recordatorios, reporte IA, chat de voz.

Ejecutar:
    pip install -r requirements.txt
    python app.py
Acceder en: http://localhost:8050
"""

import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date

import dash
from dash import dcc, html, dash_table, Input, Output, State, no_update, callback_context
import dash_bootstrap_components as dbc
from flask import request, jsonify

from database import (
    init_db, register_user, login_user,
    get_secret_question, verify_secret_answer, reset_password,
    SECURITY_QUESTIONS,
    get_categories, add_transaction, delete_transaction,
    get_transactions, get_monthly_summary, get_expenses_by_category,
    get_monthly_detail,
)
from analytics import (
    get_current_balance, get_monthly_kpis, get_liquidity_alerts,
    get_reminder_alerts, get_investment_recommendations, get_cash_flow_projection,
)

# ──────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────

init_db()
from investor_profile import init_profile_table
init_profile_table()

# ── Iniciar bot de Telegram en hilo paralelo ──
import threading
import asyncio

def _run_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        from bot import build_app as build_bot_app
        bot_app = build_bot_app()
        loop.run_until_complete(bot_app.initialize())
        loop.run_until_complete(bot_app.start())
        loop.run_until_complete(bot_app.updater.start_polling(allowed_updates=["message"]))
        loop.run_forever()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Bot de Telegram falló: {e}")

_bot_thread = threading.Thread(target=_run_bot, daemon=True)
_bot_thread.start()

def is_mobile() -> bool:
    """Detecta si el request viene de un dispositivo móvil via User-Agent."""
    try:
        from flask import request as flask_request
        ua = flask_request.headers.get("User-Agent", "").lower()
        return any(k in ua for k in ["android","iphone","ipad","mobile","phone"])
    except Exception:
        return False

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    title="Finanzas Personales",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0"}],
)

# ──────────────────────────────────────────────
# Colores y helpers
# ──────────────────────────────────────────────

C = {
    "primary": "#00d4aa", "income": "#3b9eff", "expense": "#ff5c5c",
    "warning": "#ffb84d", "bg_card": "#1c2333", "bg_dark": "#10131a",
    "text": "#e0e0e0",    "muted": "#7a8595",   "border": "#2e3a4a",
}
PAPER_BG = "rgba(0,0,0,0)"; PLOT_BG = "rgba(0,0,0,0)"; GRID_COL = "#1e2a38"

def cs(border=C["border"]):
    return {"backgroundColor": C["bg_card"], "border": f"1px solid {border}", "borderRadius": "12px"}

def kpi_card(title, value, subtitle, color, icon):
    return dbc.Card(dbc.CardBody(html.Div([
        html.Span(icon, style={"fontSize": "2.2rem"}),
        html.Div([
            html.P(title,    style={"color": C["muted"],  "fontSize": "0.78rem", "margin": "0"}),
            html.H4(value,   style={"color": color,       "fontWeight": "700",   "margin": "2px 0"}),
            html.P(subtitle, style={"color": C["muted"],  "fontSize": "0.75rem", "margin": "0"}),
        ], style={"marginLeft": "14px"}),
    ], style={"display": "flex", "alignItems": "center"})), style=cs(color))

def cl(title, extra=None):
    base = dict(
        title=dict(text=title, font=dict(color=C["text"], size=13)),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=C["text"], size=11),
        xaxis=dict(gridcolor=GRID_COL, tickfont=dict(size=10)),
        yaxis=dict(gridcolor=GRID_COL, tickfont=dict(size=10)),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                    yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=30, l=30, r=10), height=320,
        autosize=True,
    )
    if extra: base.update(extra)
    return base


# ──────────────────────────────────────────────
# Layout principal
# ──────────────────────────────────────────────

def auth_panel():
    """Panel de autenticación con tabs: Ingresar / Registrarse / Recuperar contraseña."""
    CARD = {**cs(C["primary"]), "maxWidth": "480px", "margin": "60px auto 0"}

    login_tab = dbc.Tab(label="🔑  Ingresar", tab_id="auth-login", children=dbc.CardBody([
        dbc.Label("Usuario", style={"color": C["muted"]}),
        dbc.Input(id="inp-user", placeholder="Tu nombre de usuario", type="text", className="mb-2"),
        dbc.Label("Contraseña", style={"color": C["muted"]}),
        dbc.Input(id="inp-pass", placeholder="Tu contraseña", type="password", className="mb-3"),
        dbc.Button("Ingresar", id="btn-login", color="success", n_clicks=0, className="w-100"),
        html.Div(id="login-feedback", className="mt-3"),
    ]))

    register_tab = dbc.Tab(label="✏️  Registrarse", tab_id="auth-register", children=dbc.CardBody([
        dbc.Label("Usuario", style={"color": C["muted"]}),
        dbc.Input(id="inp-reg-user", placeholder="Elegí un nombre de usuario", type="text", className="mb-2"),
        dbc.Label("Contraseña", style={"color": C["muted"]}),
        dbc.Input(id="inp-reg-pass", placeholder="Contraseña (mín. 6 caracteres)", type="password", className="mb-2"),
        dbc.Label("Repetir contraseña", style={"color": C["muted"]}),
        dbc.Input(id="inp-reg-pass2", placeholder="Repetí la contraseña", type="password", className="mb-3"),
        dbc.Label("Pregunta de seguridad", style={"color": C["muted"]}),
        dcc.Dropdown(id="inp-reg-question",
            options=[{"label": q, "value": q} for q in SECURITY_QUESTIONS],
            placeholder="Seleccioná una pregunta...",
            style={"color": "#000"}, className="mb-2"),
        dbc.Label("Respuesta", style={"color": C["muted"]}),
        dbc.Input(id="inp-reg-answer", placeholder="Tu respuesta (no distingue mayúsculas)", type="text", className="mb-3"),
        dbc.Button("Crear cuenta", id="btn-register", color="primary", n_clicks=0, className="w-100"),
        html.Div(id="register-feedback", className="mt-3"),
    ]))

    recover_tab = dbc.Tab(label="🔓  Recuperar contraseña", tab_id="auth-recover", children=dbc.CardBody([
        html.P("Ingresá tu usuario para ver tu pregunta de seguridad.",
               style={"color": C["muted"], "fontSize": "0.88rem"}),
        dbc.Label("Usuario", style={"color": C["muted"]}),
        dbc.Input(id="inp-rec-user", placeholder="Tu nombre de usuario", type="text", className="mb-2"),
        dbc.Button("Buscar pregunta", id="btn-rec-find", color="secondary", n_clicks=0, className="mb-3"),
        html.Div(id="rec-question-area"),
    ]))

    return html.Div([
        html.Div([
            html.H2("💰 Finanzas Personales",
                    style={"color": C["primary"], "fontWeight": "800", "textAlign": "center", "margin": "0"}),
            html.P("Gestión inteligente de tu dinero",
                   style={"color": C["muted"], "textAlign": "center", "marginBottom": "24px"}),
        ], style={"paddingTop": "40px"}),
        dbc.Card(
            dbc.Tabs([login_tab, register_tab, recover_tab],
                     id="auth-tabs", active_tab="auth-login"),
            style=CARD),
    ])


app.layout = dbc.Container([
    # Stores y helpers siempre presentes
    dcc.Store(id="active-user-id",     data=None),
    dcc.Store(id="saved-flag",         data=0),
    dcc.Store(id="voice-result-store", data=None),
    dcc.Store(id="rec-verified-user",  data=None),
    dcc.Store(id="report-data-store",  data=None),
    dcc.Store(id="report-text-store",  data=None),
    dcc.Interval(id="voice-poll-interval", interval=500, n_intervals=0),
    html.Div(id="voice-start-dummy", style={"display": "none"}),
    html.Div(id="voice-stop-dummy",  style={"display": "none"}),

    # Contenido principal (auth o app)
    html.Div(id="main-content", children=auth_panel()),

    # Toast
    dbc.Toast(id="toast-msg", header="", is_open=False, duration=3500,
              style={"position":"fixed","top":20,"right":20,"zIndex":9999,"minWidth":"280px"}),
    dcc.Download(id="download-excel"),
], fluid=True, style={"backgroundColor": C["bg_dark"], "minHeight": "100vh", "padding": "0 24px 40px"})


# ──────────────────────────────────────────────
# Auth callbacks
# ──────────────────────────────────────────────

def _build_app_layout(username, user_id):
    header = html.Div([
        html.H2("💰 Finanzas Personales",
                style={"color": C["primary"], "fontWeight": "800", "margin": "0", "display": "inline"}),
        dbc.Button("Cerrar sesión", id="btn-logout", color="outline-secondary", size="sm",
                   n_clicks=0, style={"float": "right", "marginTop": "4px"}),
        html.P(f"Bienvenido, {username}", style={"color": C["muted"], "margin": "0"}),
    ], style={"padding": "18px 0 10px", "borderBottom": f"1px solid {C['border']}", "marginBottom": "16px"})

    tabs = dbc.Tabs([
        dbc.Tab(label="📊  Dashboard",       tab_id="dashboard"),
        dbc.Tab(label="💳  Transacciones",   tab_id="transactions"),
        dbc.Tab(label="🚨  Alertas",         tab_id="alerts"),
        dbc.Tab(label="📈  Inversiones",     tab_id="investor"),
        dbc.Tab(label="📋  Reporte IA",      tab_id="report"),
        dbc.Tab(label="🎙️  Voz",            tab_id="voice"),
    ], id="main-tabs", active_tab="dashboard", className="mb-4")

    return html.Div([header, tabs, html.Div(id="tab-content")])


# — Login —
@app.callback(
    Output("active-user-id", "data"),
    Output("main-content",   "children"),
    Output("login-feedback", "children"),
    Input("btn-login",       "n_clicks"),
    State("inp-user", "value"),
    State("inp-pass", "value"),
    prevent_initial_call=True,
)
def cb_login(n, username, password):
    if not username or not username.strip():
        return no_update, no_update, dbc.Alert("Ingresá un nombre de usuario.", color="warning")
    if not password:
        return no_update, no_update, dbc.Alert("Ingresá una contraseña.", color="warning")
    username = username.strip()
    user_id, err = login_user(username, password)
    if user_id is None:
        return no_update, no_update, dbc.Alert(err, color="danger")
    return user_id, _build_app_layout(username, user_id), no_update


# — Registro —
@app.callback(
    Output("active-user-id",    "data",     allow_duplicate=True),
    Output("main-content",      "children", allow_duplicate=True),
    Output("register-feedback", "children"),
    Input("btn-register", "n_clicks"),
    State("inp-reg-user",     "value"),
    State("inp-reg-pass",     "value"),
    State("inp-reg-pass2",    "value"),
    State("inp-reg-question", "value"),
    State("inp-reg-answer",   "value"),
    prevent_initial_call=True,
)
def cb_register(n, username, password, password2, question, answer):
    if not all([username, password, password2, question, answer]):
        return no_update, no_update, dbc.Alert("Completá todos los campos.", color="warning")
    username = username.strip()
    if len(password) < 6:
        return no_update, no_update, dbc.Alert("La contraseña debe tener al menos 6 caracteres.", color="warning")
    if password != password2:
        return no_update, no_update, dbc.Alert("Las contraseñas no coinciden.", color="danger")
    user_id, err = register_user(username, password, question, answer.strip())
    if err:
        return no_update, no_update, dbc.Alert(err, color="danger")
    return user_id, _build_app_layout(username, user_id), no_update


# — Cerrar sesión —
@app.callback(
    Output("active-user-id", "data",     allow_duplicate=True),
    Output("main-content",   "children", allow_duplicate=True),
    Input("btn-logout",      "n_clicks"),
    prevent_initial_call=True,
)
def cb_logout(n):
    if not n: return no_update, no_update
    return None, auth_panel()


# — Recupero: buscar pregunta —
@app.callback(
    Output("rec-question-area", "children"),
    Output("rec-verified-user", "data"),
    Input("btn-rec-find", "n_clicks"),
    State("inp-rec-user", "value"),
    prevent_initial_call=True,
)
def cb_rec_find(n, username):
    if not username or not username.strip():
        return dbc.Alert("Ingresá tu usuario.", color="warning"), no_update
    question, err = get_secret_question(username.strip())
    if err:
        return dbc.Alert(err, color="danger"), no_update
    form = html.Div([
        dbc.Alert([html.Strong("Pregunta: "), question], color="info", className="mb-3"),
        dbc.Label("Tu respuesta", style={"color": C["muted"]}),
        dbc.Input(id="inp-rec-answer", placeholder="Respondé la pregunta...", type="text", className="mb-2"),
        dbc.Label("Nueva contraseña", style={"color": C["muted"]}),
        dbc.Input(id="inp-rec-newpass", placeholder="Nueva contraseña (mín. 6 caracteres)", type="password", className="mb-2"),
        dbc.Label("Repetir nueva contraseña", style={"color": C["muted"]}),
        dbc.Input(id="inp-rec-newpass2", placeholder="Repetí la nueva contraseña", type="password", className="mb-3"),
        dbc.Button("Cambiar contraseña", id="btn-rec-reset", color="warning", n_clicks=0),
        html.Div(id="rec-reset-feedback", className="mt-3"),
    ])
    return form, username.strip()


# — Recupero: resetear contraseña —
@app.callback(
    Output("rec-reset-feedback", "children"),
    Input("btn-rec-reset", "n_clicks"),
    State("rec-verified-user", "data"),
    State("inp-rec-answer",   "value"),
    State("inp-rec-newpass",  "value"),
    State("inp-rec-newpass2", "value"),
    prevent_initial_call=True,
)
def cb_rec_reset(n, username, answer, newpass, newpass2):
    if not all([username, answer, newpass, newpass2]):
        return dbc.Alert("Completá todos los campos.", color="warning")
    if len(newpass) < 6:
        return dbc.Alert("La contraseña debe tener al menos 6 caracteres.", color="warning")
    if newpass != newpass2:
        return dbc.Alert("Las contraseñas no coinciden.", color="danger")
    _, err = verify_secret_answer(username, answer)
    if err:
        return dbc.Alert(err, color="danger")
    reset_password(username, newpass)
    return dbc.Alert("✅ Contraseña cambiada exitosamente. Ingresá con tu nueva contraseña.",
                     color="success")


# ──────────────────────────────────────────────
# Render de tabs
# ──────────────────────────────────────────────

@app.callback(
    Output("tab-content",    "children"),
    Input("main-tabs",       "active_tab"),
    Input("saved-flag",      "data"),
    State("active-user-id",  "data"),
)
def render_tab(tab, _, uid):
    if not uid: return html.Div()
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
    if trigger == "saved-flag" and tab in ["report", "voice"]:
        return no_update
    mobile = is_mobile()
    if tab == "dashboard":    return build_dashboard(uid, mobile)
    if tab == "transactions": return build_transactions(uid)
    if tab == "alerts":       return build_alerts(uid)
    if tab == "investor":     return build_investor(uid)
    if tab == "report":       return build_report(uid)
    if tab == "voice":        return build_voice(uid)
    return html.Div()


# ══════════════════════════════════════════════
# TAB 1 — Dashboard
# ══════════════════════════════════════════════

def build_dashboard(uid, mobile=False):
    ym   = datetime.now().strftime("%Y-%m")
    kpis = get_monthly_kpis(uid, ym)
    bal  = get_current_balance(uid)

    kpi_row = dbc.Row([
        dbc.Col(kpi_card("Restante del Mes", f"${kpis['income']-kpis['expense']:,.2f}", ym, C["primary"], "💰"), md=3, sm=6, className="mb-3"),
        dbc.Col(kpi_card("Ingresos del Mes", f"${kpis['income']:,.2f}",    ym,                  C["income"],  "📥"), md=3, sm=6, className="mb-3"),
        dbc.Col(kpi_card("Gastos del Mes",   f"${kpis['expense']:,.2f}",   ym,                  C["expense"], "📤"), md=3, sm=6, className="mb-3"),
        dbc.Col(kpi_card("Tasa de Ahorro",   f"{kpis['savings_rate']:.1f}%","Del ingreso",      C["warning"], "💹"), md=3, sm=6, className="mb-3"),
    ], className="mb-2")

    graph_cfg = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}

    mdf = get_monthly_summary(uid)
    fb  = go.Figure()
    if not mdf.empty:
        if mobile:
            _now = datetime.now()
            window = []
            for delta in [-1, 0, 1, 2]:
                _m = _now.month + delta
                _y = _now.year
                while _m > 12: _m -= 12; _y += 1
                while _m < 1:  _m += 12; _y -= 1
                window.append(f"{_y}-{_m:02d}")
            mdf_f = mdf[mdf["month"].isin(window)] if not mdf.empty else mdf
        else:
            mdf_f = mdf
        fb.add_trace(go.Bar(name="Ingresos", x=mdf_f[mdf_f.type=="income"]["month"],  y=mdf_f[mdf_f.type=="income"]["total"],  marker_color=C["income"],  opacity=0.85, marker_line_width=0))
        fb.add_trace(go.Bar(name="Gastos",   x=mdf_f[mdf_f.type=="expense"]["month"], y=mdf_f[mdf_f.type=="expense"]["total"], marker_color=C["expense"], opacity=0.85, marker_line_width=0))

    if mobile:
        fb.update_layout(**cl("Ing. vs Gastos", {
            "barmode": "group", "height": 280,
            "dragmode": False,
            "margin": dict(t=40, b=50, l=30, r=10),
            "font": dict(size=10),
            "xaxis": dict(tickangle=-35, tickfont=dict(size=9), gridcolor=GRID_COL),
            "yaxis": dict(tickfont=dict(size=9), gridcolor=GRID_COL),
            "legend": dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
        }))
    else:
        fb.update_layout(**cl("Ingresos vs Gastos por Mes", {"barmode": "group"}))

    today = datetime.now()
    cdf   = get_expenses_by_category(uid, today.replace(day=1).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    if not cdf.empty:
        fp = px.pie(cdf, values="total", names="category", hole=0.42,
                    color_discrete_sequence=px.colors.qualitative.Pastel)
        if mobile:
            fp.update_traces(textposition="outside", textinfo="percent",
                             textfont_size=10,
                             pull=[0.05]*len(cdf))
            fp.update_layout(**cl(f"Rubros ({ym})", {
                "height": 320,
                "margin": dict(t=40, b=60, l=10, r=10),
                "legend": dict(orientation="h", y=-0.2, x=0.5,
                               xanchor="center", font=dict(size=9)),
                "showlegend": True,
            }))
        else:
            fp.update_traces(textposition="inside", textinfo="percent+label")
            fp.update_layout(**cl(f"Gastos por Rubro ({ym})"))
    else:
        fp = go.Figure()
        fp.update_layout(**cl(f"Gastos por Rubro ({ym}) — Sin datos"))

    # ── Balance projection using simple avg savings rate per month ──
    # Solo meses reales (hasta el mes actual) para evitar distorsión de meses proyectados
    current_ym = datetime.now().strftime("%Y-%m")
    mdf_all = get_monthly_summary(uid)
    avg_savings_rate = 0.0
    if not mdf_all.empty:
        # Filtrar solo meses reales <= mes actual
        real_months = sorted([m for m in mdf_all["month"].unique() if m <= current_ym])
        rates = []
        for m in real_months:
            inc = float(mdf_all[(mdf_all["month"]==m) & (mdf_all["type"]=="income")]["total"].sum())
            exp = float(mdf_all[(mdf_all["month"]==m) & (mdf_all["type"]=="expense")]["total"].sum())
            if inc > 0 and exp > 0:
                # Tasa mensual individual: (ingreso - gasto) / ingreso
                rates.append((inc - exp) / inc)
        # Promedio simple: suma de tasas / cantidad de meses reales
        avg_savings_rate = sum(rates) / len(rates) if rates else 0.0

    proj = get_cash_flow_projection(uid, 3, 4)
    # Override future balance using avg savings rate applied to projected income
    running = 0.0
    for i, p in enumerate(proj):
        if not p["is_future"]:
            running = p["balance"]
        else:
            # Use avg savings rate * projected income as net for future months
            projected_net = p["income"] * avg_savings_rate if p["income"] > 0 else p["net"]
            running += projected_net
            proj[i] = {**p, "net": projected_net, "balance": running}

    pf   = pd.DataFrame(proj)
    fl   = go.Figure()
    if not pf.empty:
        past = pf[~pf.is_future]; fut = pf[pf.is_future]
        fl.add_trace(go.Scatter(x=past.month, y=past.balance, name="Balance real",
            line=dict(color=C["primary"], width=2.5), fill="tozeroy", fillcolor="rgba(0,212,170,0.08)"))
        if not fut.empty:
            fl.add_trace(go.Scatter(x=pd.concat([past.tail(1), fut]).month,
                y=pd.concat([past.tail(1), fut]).balance, name="Proyectado",
                line=dict(color=C["warning"], width=2, dash="dot")))
    if mobile:
        fl.update_layout(**cl("Balance", {
            "height": 250,
            "margin": dict(t=40, b=40, l=30, r=10),
            "font": dict(size=10),
            "xaxis": dict(tickangle=-35, tickfont=dict(size=9), gridcolor=GRID_COL, fixedrange=True),
            "yaxis": dict(tickfont=dict(size=9), gridcolor=GRID_COL, fixedrange=True),
            "legend": dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
        }))
    else:
        fl.update_layout(**cl("Evolución del Balance", {"height": 300}))

    # ── Monthly detail table ──
    det_rows = [{"Mes": p["month"],
                 "Ingresos": f"${p['income']:,.2f}",
                 "Gastos":   f"${p['expense']:,.2f}",
                 "Neto":     f"${p['net']:,.2f}",
                 "Balance":  f"${p['balance']:,.2f}",
                 "Estado":   "🔮 Proyectado" if p["is_future"] else "✅ Real"} for p in proj]
    detail_table = dbc.Card([
        dbc.CardHeader(html.H6("📅  Detalle Mensual", style={"color":C["primary"],"margin":"0","fontWeight":"700"})),
        dbc.CardBody(dash_table.DataTable(
            data=det_rows,
            columns=[{"name":n,"id":n} for n in ["Mes","Ingresos","Gastos","Neto","Balance","Estado"]],
            style_table={"overflowX":"auto"},
            style_cell={"backgroundColor":C["bg_card"],"color":C["text"],"textAlign":"center",
                        "padding":"9px","border":f"1px solid {C['border']}"},
            style_header={"backgroundColor":C["bg_dark"],"color":C["primary"],"fontWeight":"700","border":f"1px solid {C['border']}"},
            style_data_conditional=[
                {"if":{"filter_query":'{Estado} contains "Proyectado"'},"backgroundColor":"#1a1f15"},
                {"if":{"filter_query":'{Neto} contains "-"'},"color":C["expense"]},
            ],
        )),
    ], style=cs(), className="mb-3")

    txs = get_transactions(uid)[:8]
    # Mobile: tabla simplificada con menos columnas
    if mobile:
        tbl_data    = [{"Tipo": "▲" if t[1]=="income" else "▼",
                        "Monto": f"${t[2]:,.0f}", "Cat.": t[3] or "—", "Fecha": t[5][-5:]} for t in txs]
        tbl_columns = [{"name": n, "id": n} for n in ["Tipo","Monto","Cat.","Fecha"]]
        cell_style  = {"backgroundColor":C["bg_card"],"color":C["text"],"padding":"6px 8px",
                       "border":f"1px solid {C['border']}","fontSize":"0.82rem"}
    else:
        tbl_data    = [{"Tipo": "▲ Ingreso" if t[1]=="income" else "▼ Gasto", "Monto": f"${t[2]:,.2f}",
                        "Categoría": t[3] or "—", "Descripción": t[4] or "—", "Fecha": t[5]} for t in txs]
        tbl_columns = [{"name": n, "id": n} for n in ["Tipo","Monto","Categoría","Descripción","Fecha"]]
        cell_style  = {"backgroundColor":C["bg_card"],"color":C["text"],"padding":"9px 12px",
                       "border":f"1px solid {C['border']}","fontSize":"0.88rem"}

    tbl = dash_table.DataTable(
        data=tbl_data, columns=tbl_columns,
        style_table={"overflowX":"auto"},
        style_cell=cell_style,
        style_header={"backgroundColor":C["bg_dark"],"color":C["primary"],"fontWeight":"700","border":f"1px solid {C['border']}"},
        style_data_conditional=[
            {"if":{"filter_query":'{Tipo} contains "▲"'},"color":C["income"]},
            {"if":{"filter_query":'{Tipo} contains "▼"'},"color":C["expense"]},
        ],
    )

    if mobile:
        return html.Div([
            kpi_row,
            dbc.Card(dbc.CardBody(dcc.Graph(figure=fb, config=graph_cfg, responsive=True)), style=cs(), className="mb-3"),
            dbc.Card(dbc.CardBody(dcc.Graph(figure=fp, config=graph_cfg, responsive=True)), style=cs(), className="mb-3"),
            dbc.Card(dbc.CardBody(dcc.Graph(figure=fl, config=graph_cfg, responsive=True)), style=cs(), className="mb-3"),
            detail_table,
            dbc.Card([
                dbc.CardHeader(html.H6("Últimas Transacciones", style={"color":C["primary"],"margin":"0"})),
                dbc.CardBody(tbl if txs else html.P("Sin transacciones.", style={"color":C["muted"]})),
            ], style=cs()),
        ])

    return html.Div([
        kpi_row,
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=fb, config=graph_cfg, responsive=True)), style=cs()), md=7, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=fp, config=graph_cfg, responsive=True)), style=cs()), md=5, className="mb-3"),
        ]),
        dbc.Card(dbc.CardBody(dcc.Graph(figure=fl, config=graph_cfg, responsive=True)), style=cs(), className="mb-3"),
        detail_table,
        dbc.Card([
            dbc.CardHeader(html.H6("Últimas Transacciones", style={"color":C["primary"],"margin":"0"})),
            dbc.CardBody(tbl if txs else html.P("Sin transacciones.", style={"color":C["muted"]})),
        ], style=cs()),
    ])


# ══════════════════════════════════════════════
# TAB 2 — Transacciones
# ══════════════════════════════════════════════

def build_transactions(uid):
    exp_cats = get_categories(uid, "expense")
    def opts(cats, e): return [{"label": f"{e} {c[1]}", "value": c[0]} for c in cats]
    txs = get_transactions(uid)

    form = dbc.Card([
        dbc.CardHeader(html.H6("➕  Nueva Transacción", style={"color":C["primary"],"margin":"0","fontWeight":"700"})),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([dbc.Label("Tipo",style={"color":C["muted"]}),
                         dbc.RadioItems(id="t-type",options=[{"label":"📥 Ingreso","value":"income"},{"label":"📤 Gasto","value":"expense"}],value="expense",inline=True)], md=4),
                dbc.Col([dbc.Label("Monto ($)",style={"color":C["muted"]}),
                         dbc.Input(id="t-amount",type="number",placeholder="0.00",min=0,step="0.01")], md=4),
                dbc.Col([dbc.Label("Fecha",style={"color":C["muted"]}),
                         dbc.Input(id="t-date",type="date",value=date.today().isoformat())], md=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([dbc.Label("Categoría",style={"color":C["muted"]}),
                         dcc.Dropdown(id="t-category",options=opts(exp_cats,"💸"),placeholder="Seleccionar...",style={"color":"#000"})], md=4),
                dbc.Col([dbc.Label("Descripción",style={"color":C["muted"]}),
                         dbc.Input(id="t-desc",type="text",placeholder="Ej: Supermercado Día")], md=8),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(dbc.Checklist(id="t-recurring",
                    options=[{"label":"  Programar como pago recurrente","value":"yes"}],value=[]), md=6),
                dbc.Col(html.Div([dbc.Label("Repetir (meses)",style={"color":C["muted"]}),
                    dbc.Input(id="t-months",type="number",value=3,min=1,max=24)],
                    id="recurring-div",style={"display":"none"}), md=3),
                dbc.Col(dbc.Checklist(id="t-reminder",
                    options=[{"label":"  🔔 Recordatorio 24hs antes","value":"yes"}],value=[]), md=3),
            ], className="mb-3"),
            dbc.Button("💾  Guardar", id="btn-save", color="success", n_clicks=0),
            html.Div(id="t-feedback", className="mt-3"),
        ]),
    ], style=cs(C["primary"]), className="mb-4")

    table_card = dbc.Card([
        dbc.CardHeader(html.H6("📋  Historial", style={"color":C["primary"],"margin":"0","fontWeight":"700"})),
        dbc.CardBody(dash_table.DataTable(
            id="tx-table", data=_tx_rows(txs), page_size=15,
            columns=[{"name":n,"id":n} for n in ["ID","Tipo","Monto","Categoría","Descripción","Fecha","Prog.","🔔"]],
            row_deletable=True, filter_action="native", sort_action="native",
            style_table={"overflowX":"auto"},
            style_cell={"backgroundColor":C["bg_card"],"color":C["text"],"padding":"8px 12px","border":f"1px solid {C['border']}","fontSize":"0.87rem"},
            style_header={"backgroundColor":C["bg_dark"],"color":C["primary"],"fontWeight":"700","border":f"1px solid {C['border']}"},
            style_data_conditional=[
                {"if":{"filter_query":'{Tipo} = "INGRESO"'},"color":C["income"]},
                {"if":{"filter_query":'{Tipo} = "GASTO"'},  "color":C["expense"]},
            ],
        )),
    ], style=cs())
    return html.Div([form, table_card])

def _tx_rows(txs):
    return [{"ID":t[0],"Tipo":"INGRESO" if t[1]=="income" else "GASTO","Monto":f"${t[2]:,.2f}",
             "Categoría":t[3] or "—","Descripción":t[4] or "—","Fecha":t[5],
             "Prog.":"✓" if t[6] else "","🔔":"✓" if t[7] else ""} for t in txs]


# ══════════════════════════════════════════════
# TAB 3 — Flujo de Fondos
# ══════════════════════════════════════════════

def build_cashflow(uid, mobile=False):
    # Mobile: menos meses para mayor claridad
    back, ahead = (1, 3) if mobile else (2, 6)
    proj = get_cash_flow_projection(uid, back, ahead)
    pf   = pd.DataFrame(proj)
    fig  = go.Figure()
    graph_cfg = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}

    if not pf.empty:
        past = pf[~pf.is_future]; fut = pf[pf.is_future]
        fig.add_trace(go.Bar(x=pf.month, y=pf.income,               name="Ingresos",   marker_color=C["income"],  opacity=0.75, marker_line_width=0, yaxis="y"))
        fig.add_trace(go.Bar(x=pf.month, y=[-e for e in pf.expense], name="Gastos (−)", marker_color=C["expense"], opacity=0.75, marker_line_width=0, yaxis="y"))
        fig.add_trace(go.Scatter(x=past.month, y=past.balance, name="Balance real", yaxis="y2", line=dict(color=C["primary"],width=2.5)))
        if not fut.empty:
            join = pd.concat([past.tail(1), fut])
            fig.add_trace(go.Scatter(x=join.month, y=join.balance, name="Proyectado", yaxis="y2", line=dict(color=C["warning"],width=2,dash="dot")))
            if not mobile:
                fig.add_vrect(x0=fut.iloc[0].month, x1=pf.iloc[-1].month,
                              fillcolor="rgba(255,184,77,0.05)", line_width=0,
                              annotation_text="▶ Proyectado", annotation_position="top left",
                              annotation_font_color=C["warning"])

    if mobile:
        fig.update_layout(**cl("Flujo de Fondos", {
            "barmode": "relative", "height": 300,
            "dragmode": False,
            "margin": dict(t=40, b=50, l=30, r=10),
            "font": dict(size=10),
            "xaxis": dict(tickangle=-35, tickfont=dict(size=9), gridcolor=GRID_COL, fixedrange=True),
            "yaxis": dict(title="", tickfont=dict(size=9), gridcolor=GRID_COL, fixedrange=True),
            "yaxis2": dict(title="", overlaying="y", side="right", showgrid=False, tickfont=dict(size=9), fixedrange=True),
            "legend": dict(orientation="h", y=1.12, x=0, font=dict(size=9)),
        }))
    else:
        fig.update_layout(**cl("Flujo de Fondos", {
            "barmode": "relative", "height": 420,
            "yaxis":  dict(title="Ingresos / Gastos", gridcolor=GRID_COL),
            "yaxis2": dict(title="Balance", overlaying="y", side="right", showgrid=False),
        }))

    # Tabla: en mobile mostrar columnas reducidas
    if mobile:
        rows = [{"Mes": p["month"], "Ing.": f"${p['income']:,.0f}",
                 "Gas.": f"${p['expense']:,.0f}", "Balance": f"${p['balance']:,.0f}",
                 "Estado": "🔮" if p["is_future"] else "✅"} for p in proj]
        tbl_cols = [{"name": n, "id": n} for n in ["Mes","Ing.","Gas.","Balance","Estado"]]
        cell_pad = "6px"
        cell_fs  = "0.80rem"
    else:
        rows = [{"Mes": p["month"], "Ingresos": f"${p['income']:,.2f}", "Gastos": f"${p['expense']:,.2f}",
                 "Neto": f"${p['net']:,.2f}", "Balance": f"${p['balance']:,.2f}",
                 "Estado": "🔮 Proyectado" if p["is_future"] else "✅ Real"} for p in proj]
        tbl_cols = [{"name": n, "id": n} for n in ["Mes","Ingresos","Gastos","Neto","Balance","Estado"]]
        cell_pad = "9px"
        cell_fs  = "inherit"

    return html.Div([
        dbc.Card(dbc.CardBody(dcc.Graph(figure=fig, config=graph_cfg, responsive=True)), style=cs(), className="mb-4"),
        dbc.Card([
            dbc.CardHeader(html.H6("Detalle mensual", style={"color":C["primary"],"margin":"0"})),
            dbc.CardBody(dash_table.DataTable(data=rows, columns=tbl_cols,
                style_table={"overflowX":"auto"},
                style_cell={"backgroundColor":C["bg_card"],"color":C["text"],"textAlign":"center",
                             "padding":cell_pad,"border":f"1px solid {C['border']}","fontSize":cell_fs},
                style_header={"backgroundColor":C["bg_dark"],"color":C["primary"],"fontWeight":"700","border":f"1px solid {C['border']}"},
                style_data_conditional=[
                    {"if":{"filter_query":'{Estado} contains "Proyectado"'},"backgroundColor":"#1a1f15"},
                    {"if":{"filter_query":'{Estado} = "🔮"'},               "backgroundColor":"#1a1f15"},
                    {"if":{"filter_query":'{Neto} contains "-"'},           "color":C["expense"]},
                ])),
        ], style=cs()),
    ])


# ══════════════════════════════════════════════
# TAB 4 — Alertas
# ══════════════════════════════════════════════

def build_alerts(uid):
    reminders = get_reminder_alerts(uid)
    liquidity = get_liquidity_alerts(uid, months_ahead=4)

    rem_section = html.Div()
    if reminders:
        rem_section = html.Div([
            html.H5("🔔  Recordatorios", style={"color":"white","marginBottom":"12px"}),
            *[dbc.Alert(a["message"], color="info", className="mb-2") for a in reminders],
            html.Hr(),
        ])

    if not liquidity:
        liq_section = dbc.Alert([
            html.H5("✅  Sin alertas de liquidez", className="alert-heading"), html.Hr(),
            html.P("El flujo de fondos proyectado se ve saludable en los próximos meses."),
        ], color="success")
    else:
        liq_section = html.Div([
            *[dbc.Alert(a["message"], color="danger" if a["severity"]=="danger" else "warning", className="mb-3")
              for a in liquidity],
            dbc.Card([
                dbc.CardHeader(html.H6("💡  Consejos de liquidez", style={"color":C["warning"],"margin":"0"})),
                dbc.CardBody(html.Ul([
                    html.Li("Identificá gastos no esenciales y reducí los que puedas."),
                    html.Li("Adelantá cobros pendientes o buscá ingresos adicionales."),
                    html.Li("Negociá plazos de pago con proveedores."),
                    html.Li("Mantené un fondo de emergencia de 3 meses de gastos fijos."),
                ], style={"color":C["text"]})),
            ], style=cs(C["warning"])),
        ])

    return html.Div([
        html.H5("🚨  Alertas", style={"color":"white","marginBottom":"20px"}),
        rem_section,
        html.H5("💧  Liquidez", style={"color":"white","marginBottom":"12px"}),
        liq_section,
    ])


# ══════════════════════════════════════════════
# TAB 5 — Inversiones
# ══════════════════════════════════════════════

def build_investments(uid):
    bal  = get_current_balance(uid)
    kpis = get_monthly_kpis(uid)
    surp = max(0.0, bal)
    recs = get_investment_recommendations(surp)
    RC   = {"Muy Bajo":"success","Bajo":"info","Bajo–Medio":"info","Medio":"warning",
            "Medio–Alto":"warning","Alto":"danger","Diversificado":"primary","—":"secondary"}

    summary = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.P("Capital disponible",style={"color":C["muted"],"fontSize":"0.8rem","margin":"0"}),html.H3(f"${surp:,.2f}",style={"color":C["primary"],"margin":"4px 0"})]),style=cs(C["primary"])),md=4,className="mb-3"),
        dbc.Col(dbc.Card(dbc.CardBody([html.P("Perfil sugerido",style={"color":C["muted"],"fontSize":"0.8rem","margin":"0"}),html.H4("Moderado" if surp>200_000 else "Conservador",style={"color":C["warning"],"margin":"4px 0"})]),style=cs(C["warning"])),md=4,className="mb-3"),
        dbc.Col(dbc.Card(dbc.CardBody([html.P("Tasa de ahorro mensual",style={"color":C["muted"],"fontSize":"0.8rem","margin":"0"}),html.H4(f"{kpis['savings_rate']:.1f} %",style={"color":C["income"],"margin":"4px 0"})]),style=cs(C["income"])),md=4,className="mb-3"),
    ], className="mb-3")

    cols = [dbc.Col(dbc.Card(dbc.CardBody([
        html.H3(r["icon"],style={"marginBottom":"8px"}),
        html.H6(r["title"],style={"color":"white","fontWeight":"700"}),
        html.P(r["description"],style={"color":C["muted"],"fontSize":"0.83rem"}),
        dbc.Badge(f"Riesgo: {r.get('risk','—')}",color=RC.get(r.get("risk","—"),"secondary"),className="mt-auto"),
    ],style={"display":"flex","flexDirection":"column","height":"100%"}),style={**cs(),"height":"100%"}),md=4,className="mb-3") for r in recs]

    return html.Div([
        html.H5("📈  Recomendaciones de Inversión",style={"color":"white","marginBottom":"18px"}),
        summary, dbc.Row(cols),
        dbc.Alert([html.Strong("⚠️  Aviso: "),"Recomendaciones orientativas. Consultá un asesor certificado antes de invertir."],color="secondary",className="mt-2"),
    ])


# ══════════════════════════════════════════════
# TAB 6 — Reporte IA
# ══════════════════════════════════════════════

def _month_options(n=12):
    opts = []; today = datetime.now()
    names = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    for i in range(1, n + 1):
        m = today.month - i; y = today.year
        while m <= 0: m += 12; y -= 1
        opts.append({"label": f"{names[m-1]} {y}", "value": f"{y}-{m:02d}"})
    return opts

def build_report(uid):
    return html.Div([
        html.H5("📋  Reporte Mensual con IA", style={"color":"white","marginBottom":"18px"}),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Seleccioná el mes", style={"color":C["muted"]}),
                        dcc.Dropdown(id="report-month", options=_month_options(),
                                     placeholder="Seleccioná un mes...",
                                     style={"color":"#000"}, clearable=False),
                    ], md=4),
                    dbc.Col(dbc.Button("📊  Generar Reporte", id="btn-report",
                                       color="primary", n_clicks=0,
                                       style={"marginTop":"24px"}), md=3),
                    dbc.Col(dbc.Button("📥  Descargar Excel", id="btn-download-excel",
                                       color="success", n_clicks=0,
                                       style={"marginTop":"24px"}), md=3),
                ]),
            ])
        ], style=cs(C["primary"]), className="mb-4"),

        dcc.Loading(html.Div(id="report-output"), type="circle",
                    color=C["primary"]),

    ])


# ══════════════════════════════════════════════
# TAB 7 — Chat de Voz
# ══════════════════════════════════════════════

def build_voice(uid):
    cats     = get_categories(uid)
    cat_opts = [{"label": c[1], "value": c[0]} for c in cats]

    instructions = dbc.Alert([
        html.H6("📋  Instrucciones", className="alert-heading"),
        html.P("Hacé clic en Iniciar, hablá claramente y luego detené la grabación. Ejemplos:"),
        html.Ul([
            html.Li('"Gasté 1500 pesos en el supermercado hoy"'),
            html.Li('"Cobré 80000 de sueldo"'),
            html.Li('"Pagué 15000 de alquiler ayer"'),
        ], style={"marginBottom": "0"}),
    ], color="info")

    controls = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col(dbc.Button("🎙️  Iniciar Grabación", id="btn-start-record",
                                   color="danger", n_clicks=0), width="auto"),
                dbc.Col(dbc.Button("⏹️  Detener",          id="btn-stop-record",
                                   color="secondary", n_clicks=0), width="auto"),
                dbc.Col(html.Div("● En espera", id="voice-status",
                                 style={"color":C["muted"],"paddingTop":"8px","fontWeight":"600"})),
            ], align="center"),
        ])
    ], style=cs(), className="mb-3")

    form = dbc.Card([
        dbc.CardHeader(html.H6("💳  Transacción Detectada", style={"color":C["primary"],"margin":"0","fontWeight":"700"})),
        dbc.CardBody([
            dbc.Card([
                dbc.CardHeader("📝 Transcripción"),
                dbc.CardBody(html.P("—", id="voice-transcript-text",
                                    style={"color":C["muted"],"fontStyle":"italic","margin":"0"})),
            ], style=cs(), className="mb-3", id="voice-transcript-card"),

            dbc.Row([
                dbc.Col([dbc.Label("Tipo",style={"color":C["muted"]}),
                         dbc.RadioItems(id="t-voice-type",
                             options=[{"label":"📥 Ingreso","value":"income"},{"label":"📤 Gasto","value":"expense"}],
                             value="expense", inline=True)], md=4),
                dbc.Col([dbc.Label("Monto ($)",style={"color":C["muted"]}),
                         dbc.Input(id="t-voice-amount",type="number",value=0,min=0)], md=4),
                dbc.Col([dbc.Label("Fecha",style={"color":C["muted"]}),
                         dbc.Input(id="t-voice-date",type="date",value=date.today().isoformat())], md=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([dbc.Label("Categoría",style={"color":C["muted"]}),
                         dcc.Dropdown(id="t-voice-category",options=cat_opts,style={"color":"#000"})], md=4),
                dbc.Col([dbc.Label("Descripción",style={"color":C["muted"]}),
                         dbc.Input(id="t-voice-desc",type="text")], md=8),
            ], className="mb-3"),
            dbc.Button("✅  Confirmar y Guardar", id="btn-voice-confirm",
                       color="success", n_clicks=0),
            html.Div(id="voice-confirm-feedback", className="mt-3"),
        ]),
    ], style=cs(C["primary"]))

    return html.Div([instructions, controls, form])


# ──────────────────────────────────────────────
# Callbacks de interacción — Transacciones
# ──────────────────────────────────────────────

@app.callback(Output("recurring-div","style"), Input("t-recurring","value"))
def toggle_recurring(v):
    return {"display":"block"} if v and "yes" in v else {"display":"none"}

@app.callback(Output("t-category","options"), Input("t-type","value"), State("active-user-id","data"))
def upd_cats(type_val, uid):
    if not uid: return []
    cats = get_categories(uid, type_val)
    e = "💰" if type_val=="income" else "💸"
    return [{"label":f"{e} {c[1]}","value":c[0]} for c in cats]

@app.callback(
    Output("t-feedback","children"), Output("t-amount","value"), Output("t-desc","value"),
    Output("tx-table","data"),       Output("saved-flag","data"),
    Output("toast-msg","children"),  Output("toast-msg","header"), Output("toast-msg","is_open"),
    Input("btn-save","n_clicks"),
    State("t-type","value"),    State("t-amount","value"),   State("t-category","value"),
    State("t-desc","value"),    State("t-date","value"),     State("t-recurring","value"),
    State("t-months","value"),  State("t-reminder","value"), State("saved-flag","data"),
    State("active-user-id","data"),
    prevent_initial_call=True,
)
def save_tx(n, ttype, amount, category, desc, txdate, recurring, months, reminder, flag, uid):
    if not uid: return dbc.Alert("Sin sesión.", color="danger"), amount, desc, no_update, flag,"","",False
    if not amount or not category or not txdate:
        return dbc.Alert("Completá monto, categoría y fecha.", color="warning"), amount, desc, no_update, flag,"","",False
    is_rec = "yes" in (recurring or [])
    has_rem= "yes" in (reminder  or [])
    add_transaction(uid, ttype, float(amount), int(category), desc or "", txdate, is_rec, int(months or 0), has_rem)
    new_data = _tx_rows(get_transactions(uid))
    label = "Ingreso" if ttype=="income" else "Gasto"
    msg   = f"Guardado: {label} de ${float(amount):,.2f}"
    if is_rec and months: msg += f" + {months} meses programados"
    if has_rem: msg += " · 🔔 recordatorio activado"
    return dbc.Alert(msg, color="success", duration=3000), None, None, new_data, flag+1, msg, "✅ Guardado", True

@app.callback(
    Output("tx-table","data", allow_duplicate=True),
    Input("tx-table","data_previous"), State("tx-table","data"),
    prevent_initial_call=True,
)
def del_row(prev, curr):
    if prev is None or curr is None: return no_update
    if len(prev) > len(curr):
        for tid in {r["ID"] for r in prev} - {r["ID"] for r in curr}:
            delete_transaction(int(tid))
    return curr


# ──────────────────────────────────────────────
# Callback — Reporte IA
# ──────────────────────────────────────────────

@app.callback(
    Output("report-output",     "children"),
    Output("report-data-store", "data"),
    Output("report-text-store", "data"),
    Input("btn-report","n_clicks"),
    State("report-month","value"),
    State("active-user-id","data"),
    prevent_initial_call=True,
)
def gen_report(n, month, uid):
    if not uid or not month:
        return dbc.Alert("Seleccioná un mes.", color="warning"), no_update, no_update
    try:
        from groq_utils import generate_report
        data = get_monthly_detail(uid, month)

        kpi_row = dbc.Row([
            dbc.Col(kpi_card("Ingresos",      f"${data['income']:,.2f}",      month,          C["income"],  "📥"), md=3, sm=6, className="mb-3"),
            dbc.Col(kpi_card("Gastos",         f"${data['expense']:,.2f}",    month,          C["expense"], "📤"), md=3, sm=6, className="mb-3"),
            dbc.Col(kpi_card("Balance",        f"${data['balance']:,.2f}",    "Neto del mes", C["primary"], "💰"), md=3, sm=6, className="mb-3"),
            dbc.Col(kpi_card("Tasa de Ahorro", f"{data['savings_rate']:.1f}%",
                "vs anterior: " + f"{data['savings_rate']-data['prev_savings_rate']:+.1f}pp",
                C["warning"], "💹"), md=3, sm=6, className="mb-3"),
        ], className="mb-3")

        report_text = generate_report(data)

        # Serializar data para el store (convertir tuples a listas)
        data_store = {
            **{k: v for k, v in data.items()
               if k not in ["categories","prev_categories","upcoming_payments"]},
            "categories":        [list(x) for x in data["categories"]],
            "prev_categories":   [list(x) for x in data["prev_categories"]],
            "upcoming_payments": [list(x) for x in data["upcoming_payments"]],
        }

        output = html.Div([
            kpi_row,
            dbc.Card([
                dbc.CardHeader(html.H6(f"Reporte generado por IA — {month}",
                    style={"color":C["primary"],"margin":"0","fontWeight":"700"})),
                dbc.CardBody(dcc.Markdown(report_text,
                    style={"color":C["text"],"lineHeight":"1.7","fontSize":"0.95rem"})),
            ], style=cs(C["primary"])),
        ])
        return output, data_store, report_text
    except ValueError as e:
        return dbc.Alert(str(e), color="warning"), no_update, no_update
    except Exception as e:
        return dbc.Alert(f"Error al generar el reporte: {str(e)}", color="danger"), no_update, no_update


@app.callback(
    Output("download-excel", "data"),
    Input("btn-download-excel", "n_clicks"),
    State("report-data-store",  "data"),
    State("report-text-store",  "data"),
    State("active-user-id",     "data"),
    prevent_initial_call=True,
)
def download_excel(n, data_store, report_text, uid):
    if not n or not data_store or not uid:
        return no_update
    try:
        from excel_report import generate_excel_report
        from database import get_transactions

        year_month = data_store["year_month"]
        # Reconstruir data con tuples
        data = {
            **{k: v for k, v in data_store.items()
               if k not in ["categories","prev_categories","upcoming_payments"]},
            "categories":        [tuple(x) for x in data_store["categories"]],
            "prev_categories":   [tuple(x) for x in data_store["prev_categories"]],
            "upcoming_payments": [tuple(x) for x in data_store["upcoming_payments"]],
        }

        # Obtener transacciones del mes
        start = f"{year_month}-01"
        import calendar
        y, m = map(int, year_month.split("-"))
        last_day = calendar.monthrange(y, m)[1]
        end = f"{year_month}-{last_day:02d}"
        transactions = get_transactions(uid, start_date=start, end_date=end)

        excel_bytes = generate_excel_report(transactions, data, report_text)
        filename    = f"reporte_finanzas_{year_month}.xlsx"

        return dcc.send_bytes(excel_bytes, filename)
    except Exception as e:
        return no_update


# ──────────────────────────────────────────────
# Callbacks de Voz — clientside
# ──────────────────────────────────────────────

app.clientside_callback(
    """
    function(n) {
        if (!n) return window.dash_clientside.no_update;
        var statusEl = document.getElementById('voice-status');
        var startBtn = document.getElementById('btn-start-record');
        var stopBtn  = document.getElementById('btn-stop-record');
        navigator.mediaDevices.getUserMedia({audio: true})
            .then(function(stream) {
                window._audioStream = stream;
                window._audioChunks = [];
                var opts = MediaRecorder.isTypeSupported('audio/webm') ? {mimeType:'audio/webm'} : {};
                window._mediaRecorder = new MediaRecorder(stream, opts);
                window._mediaRecorder.ondataavailable = function(e) {
                    if (e.data.size > 0) window._audioChunks.push(e.data);
                };
                window._mediaRecorder.start(100);
                if (statusEl) statusEl.innerHTML = '<span style="color:#ff5c5c">&#9679; Grabando...</span>';
                if (startBtn) startBtn.disabled = true;
                if (stopBtn)  stopBtn.disabled  = false;
            })
            .catch(function(err) {
                if (statusEl) statusEl.innerText = '❌ Error al acceder al micrófono: ' + err.message;
            });
        return window.dash_clientside.no_update;
    }
    """,
    Output("voice-start-dummy", "children"),
    Input("btn-start-record", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n, uid) {
        if (!n || !window._mediaRecorder) return window.dash_clientside.no_update;
        var statusEl = document.getElementById('voice-status');
        var startBtn = document.getElementById('btn-start-record');
        var stopBtn  = document.getElementById('btn-stop-record');
        window._mediaRecorder.onstop = function() {
            var mime = window._mediaRecorder.mimeType || 'audio/webm';
            var blob = new Blob(window._audioChunks, {type: mime});
            if (window._audioStream)
                window._audioStream.getTracks().forEach(function(t){ t.stop(); });
            var fd = new FormData();
            fd.append('audio', blob, 'recording.webm');
            fd.append('user_id', String(uid));
            if (statusEl) statusEl.innerHTML = '<span style="color:#ffb84d">&#9203; Procesando...</span>';
            fetch('/process-audio', {method:'POST', body: fd})
                .then(function(r){ return r.json(); })
                .then(function(data){
                    localStorage.setItem('_dashVoiceResult', JSON.stringify(data));
                    if (statusEl) statusEl.innerHTML = '<span style="color:#00d4aa">&#10003; Completado</span>';
                })
                .catch(function(err){
                    localStorage.setItem('_dashVoiceResult', JSON.stringify({error: String(err)}));
                    if (statusEl) statusEl.innerHTML = '<span style="color:#ff5c5c">&#10007; Error</span>';
                })
                .finally(function(){
                    if (startBtn) startBtn.disabled = false;
                    if (stopBtn)  stopBtn.disabled  = true;
                });
        };
        window._mediaRecorder.stop();
        return window.dash_clientside.no_update;
    }
    """,
    Output("voice-stop-dummy",  "children"),
    Input("btn-stop-record",    "n_clicks"),
    State("active-user-id",     "data"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n) {
        var r = localStorage.getItem('_dashVoiceResult');
        if (r) { localStorage.removeItem('_dashVoiceResult'); return JSON.parse(r); }
        return window.dash_clientside.no_update;
    }
    """,
    Output("voice-result-store", "data"),
    Input("voice-poll-interval", "n_intervals"),
)


# ──────────────────────────────────────────────
# Callback de Voz — poblar formulario
# ──────────────────────────────────────────────

@app.callback(
    Output("voice-transcript-text", "children"),
    Output("t-voice-type",          "value"),
    Output("t-voice-amount",        "value"),
    Output("t-voice-category",      "value"),
    Output("t-voice-desc",          "value"),
    Output("t-voice-date",          "value"),
    Input("voice-result-store",     "data"),
    prevent_initial_call=True,
)
def populate_voice_form(data):
    fallback = ("—", "expense", 0, None, "", date.today().isoformat())
    if not data: return fallback
    if "error" in data:
        return (f"❌ {data['error']}",) + fallback[1:]
    tx = data.get("transaction", {})
    return (
        data.get("transcription", "—"),
        tx.get("type", "expense"),
        tx.get("amount", 0),
        tx.get("category_id"),
        tx.get("description", ""),
        tx.get("date", date.today().isoformat()),
    )


# ──────────────────────────────────────────────
# Callback de Voz — confirmar y guardar
# ──────────────────────────────────────────────

@app.callback(
    Output("voice-confirm-feedback", "children"),
    Output("saved-flag", "data",     allow_duplicate=True),
    Input("btn-voice-confirm",       "n_clicks"),
    State("t-voice-type",    "value"), State("t-voice-amount",   "value"),
    State("t-voice-category","value"), State("t-voice-desc",     "value"),
    State("t-voice-date",    "value"), State("active-user-id",   "data"),
    State("saved-flag",      "data"),
    prevent_initial_call=True,
)
def confirm_voice(n, ttype, amount, category, desc, txdate, uid, flag):
    if not n or not uid: return no_update, no_update
    if not all([amount, category, txdate]):
        return dbc.Alert("Completá todos los campos.", color="warning"), no_update
    try:
        add_transaction(uid, ttype, float(amount), int(category), desc or "Voz", txdate)
        label = "Ingreso" if ttype=="income" else "Gasto"
        return dbc.Alert(f"✅ Guardado: {label} de ${float(amount):,.2f}", color="success", duration=3000), flag+1
    except Exception as e:
        return dbc.Alert(f"❌ Error: {e}", color="danger"), no_update



# ══════════════════════════════════════════════
# TAB 8 — Perfil de Inversor
# ══════════════════════════════════════════════

def build_investor(uid):
    from investor_profile import get_investor_profile, QUESTIONS, PROFILES

    existing = get_investor_profile(uid)
    if existing:
        return _render_profile_result(existing, uid, show_redo=True)
    # New user: show intro card with button to start
    return html.Div([
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Span("🤔", style={"fontSize":"3rem"}),
                html.Div([
                    html.H4("¿No sabés en qué invertir?",
                            style={"color":"white","fontWeight":"800","margin":"0"}),
                    html.P("Realizá este cuestionario para conocer tu perfil de inversor "
                           "y recibir recomendaciones personalizadas en base a tus "
                           "objetivos y preferencias.",
                           style={"color":C["muted"],"margin":"8px 0 0"}),
                ], style={"marginLeft":"18px"}),
            ], style={"display":"flex","alignItems":"flex-start","marginBottom":"20px"}),
            dbc.Button("📋  Realizar test", id="btn-start-survey",
                       color="success", size="lg", n_clicks=0),
        ]), style=cs(C["primary"]), className="mb-4"),
        html.Div(id="survey-area"),
    ])


def _profile_color(name):
    MAP = {
        "Conservador":         "#3B9EFF",
        "Conservador Moderado":"#00D4AA",
        "Moderado":            "#FFB84D",
        "Moderado Agresivo":   "#FF8C00",
        "Agresivo":            "#FF5C5C",
    }
    return MAP.get(name, C["primary"])


def _render_profile_result(result, uid, show_redo=False):
    p     = result["profile"]
    color = _profile_color(p["name"])

    asset_items = [html.Li(a, style={"color": C["text"], "marginBottom": "4px"})
                   for a in p["assets"]]

    header = dbc.Card(dbc.CardBody(html.Div([
        html.Span(p["icon"], style={"fontSize": "3rem"}),
        html.Div([
            html.P("Tu perfil de inversor",
                   style={"color": C["muted"], "fontSize": "0.85rem", "margin": "0"}),
            html.H2(p["name"], style={"color": color, "fontWeight": "800", "margin": "4px 0"}),
            html.P(f"Puntaje: {result['score']} / 100",
                   style={"color": C["muted"], "margin": "0"}),
        ], style={"marginLeft": "18px"}),
    ], style={"display": "flex", "alignItems": "center"})),
    style={**cs(color), "marginBottom": "20px"})

    alloc_card = dbc.Card(dbc.CardBody([
        html.H6("📊  Asignación sugerida",
                style={"color": color, "fontWeight": "700", "marginBottom": "8px"}),
        html.P(p["alloc"], style={"color": C["text"]}),
        html.H6("🏦  Activos recomendados",
                style={"color": color, "fontWeight": "700", "margin": "12px 0 8px"}),
        html.Ul(asset_items, style={"paddingLeft": "20px", "margin": "0"}),
    ]), style=cs(), className="mb-3")

    redo = html.Div()
    if show_redo:
        completed = result.get("completed_at", "")
        redo = html.Div([
            html.P(f"Cuestionario completado el {completed}",
                   style={"color": C["muted"], "fontSize": "0.82rem", "marginBottom": "8px"}),
            dbc.Button("🔄  Rehacer cuestionario", id="btn-redo-profile",
                       color="outline-secondary", size="sm", n_clicks=0),
            html.Div(id="redo-profile-area", className="mt-3"),
        ])

    return html.Div([header, alloc_card, redo])


def _render_questionnaire(uid, show_intro=True):
    from investor_profile import QUESTIONS

    intro = html.Div()
    if show_intro:
        intro = dbc.Alert([
            html.H5("🧠  Cuestionario de Perfil de Inversor", className="alert-heading"),
            html.P("Respondé las siguientes preguntas para determinar tu perfil. "
                   "El resultado se guarda y se usa para personalizar las recomendaciones de inversión. "
                   "La pregunta final es evaluada por IA."),
        ], color="info", className="mb-4")

    question_cards = []
    current_dim = None

    for q in QUESTIONS:
        if q["dim"] != current_dim:
            current_dim = q["dim"]
            question_cards.append(
                html.H6(f"📌  {current_dim}",
                        style={"color": C["primary"], "marginTop": "20px",
                               "marginBottom": "10px", "fontWeight": "700"}))

        if q["type"] == "single":
            opts = [{"label": label, "value": pts}
                    for pts, label in q["options"]]
            card = dbc.Card(dbc.CardBody([
                dbc.Label(q["text"],
                          style={"color": C["text"], "fontWeight": "600", "marginBottom": "10px"}),
                dbc.RadioItems(id=f"iq-{q['id']}", options=opts,
                               labelStyle={"color": C["muted"], "fontSize": "0.9rem"},
                               inputStyle={"marginRight": "8px"}),
            ]), style=cs(), className="mb-2")
        else:
            card = dbc.Card(dbc.CardBody([
                dbc.Label(q["text"],
                          style={"color": C["text"], "fontWeight": "600", "marginBottom": "10px"}),
                html.Small("Esta respuesta será evaluada por IA (0 a 15 puntos)",
                           style={"color": C["primary"], "display": "block", "marginBottom": "8px"}),
                dbc.Textarea(id=f"iq-{q['id']}", placeholder="Escribí tu respuesta aquí...",
                             style={"backgroundColor": C["bg_card"], "color": C["text"],
                                    "border": f"1px solid {C['border']}"},
                             rows=4),
            ]), style=cs(C["primary"]), className="mb-2")

        question_cards.append(card)

    submit = html.Div([
        dbc.Button("📊  Calcular mi perfil", id="btn-submit-profile",
                   color="success", n_clicks=0, size="lg", className="mt-3"),
        dcc.Loading(html.Div(id="profile-result-area", className="mt-4"),
                    type="circle", color=C["primary"]),
    ])

    return html.Div([intro] + question_cards + [submit])


# — Callbacks de Perfil de Inversor —

@app.callback(
    Output("profile-result-area", "children"),
    Input("btn-submit-profile",   "n_clicks"),
    [State(f"iq-{q['id']}", "value") for q in __import__("investor_profile").QUESTIONS],
    State("active-user-id", "data"),
    prevent_initial_call=True,
)
def submit_profile(n, *args):
    from investor_profile import QUESTIONS, calculate_profile, save_investor_profile
    states   = list(args)
    uid      = states[-1]
    q_values = states[:-1]

    if not uid or not n:
        return no_update

    missing = [QUESTIONS[i]["text"][:40] for i, v in enumerate(q_values) if v is None]
    if missing:
        return dbc.Alert(
            f"Respondé todas las preguntas. Faltan: {len(missing)}.",
            color="warning")

    answers = {q["id"]: q_values[i] for i, q in enumerate(QUESTIONS)}

    try:
        result = calculate_profile(answers)
        save_investor_profile(uid, result["score"], result["profile_name"])
        extra = []
        if result["auto_conservador"]:
            extra.append(dbc.Alert(
                "⚠️  Una de tus respuestas indica perfil Conservador automático. "
                "El puntaje fue ajustado.", color="warning", className="mb-3"))
        if result["q9_explanation"]:
            extra.append(dbc.Alert([
                html.Strong("🤖  Evaluación IA (pregunta 9): "),
                f"{result['q9_explanation']} ({result['q9_score']}/15 pts)"
            ], color="info", className="mb-3"))
        return html.Div(extra + [_render_profile_result(result, uid, show_redo=False)])
    except Exception as e:
        return dbc.Alert(f"Error al calcular perfil: {str(e)}", color="danger")


@app.callback(
    Output("redo-profile-area", "children"),
    Input("btn-redo-profile",   "n_clicks"),
    State("active-user-id",     "data"),
    prevent_initial_call=True,
)
def redo_profile(n, uid):
    if not n or not uid:
        return no_update
    return _render_questionnaire(uid, show_intro=False)


@app.callback(
    Output("survey-area", "children"),
    Input("btn-start-survey", "n_clicks"),
    State("active-user-id",   "data"),
    prevent_initial_call=True,
)
def start_survey(n, uid):
    if not n or not uid:
        return no_update
    return _render_questionnaire(uid, show_intro=False)

# ──────────────────────────────────────────────
# Flask route — procesar audio
# ──────────────────────────────────────────────

@app.server.route("/process-audio", methods=["POST"])
def process_audio():
    try:
        from groq_utils import transcribe_audio, extract_transaction
        audio_file = request.files.get("audio")
        uid        = request.form.get("user_id", type=int)
        if not audio_file or not uid:
            return jsonify({"error": "Datos incompletos"}), 400

        audio_bytes   = audio_file.read()
        transcription = transcribe_audio(audio_bytes, "webm")
        cats          = get_categories(uid)            # (id, name, type)
        transaction   = extract_transaction(transcription, cats)

        return jsonify({"transcription": transcription, "transaction": transaction})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error al procesar audio: {str(e)}"}), 500


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)