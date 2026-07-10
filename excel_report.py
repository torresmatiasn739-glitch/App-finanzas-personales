"""
excel_report.py — Generador de reporte mensual en Excel.
Hoja 1: Transacciones del mes
Hoja 2: Resumen e informe IA
"""

import io
from datetime import datetime

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter


# ──────────────────────────────────────────────
# Colores
# ──────────────────────────────────────────────
C_DARK     = "0D1117"
C_PRIMARY  = "00D4AA"
C_INCOME   = "3B9EFF"
C_EXPENSE  = "FF5C5C"
C_WARNING  = "FFB84D"
C_HEADER   = "1C2333"
C_ROW_ALT  = "161B25"
C_WHITE    = "E0E0E0"
C_MUTED    = "7A8595"
C_BORDER   = "2E3A4A"

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _font(bold=False, color=C_WHITE, size=11, italic=False):
    return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)

def _border():
    s = Side(style="thin", color=C_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)

def _center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def _left():
    return Alignment(horizontal="left", vertical="center", wrap_text=True)


# ──────────────────────────────────────────────
# Hoja 1 — Transacciones
# ──────────────────────────────────────────────

def _sheet_transactions(wb, transactions, year_month):
    ws = wb.create_sheet("Tus gastos del mes")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A3"

    # Título
    ws.merge_cells("A1:E1")
    ws["A1"] = f"Transacciones — {year_month}"
    ws["A1"].font      = _font(bold=True, color=C_PRIMARY, size=14)
    ws["A1"].fill      = _fill(C_DARK)
    ws["A1"].alignment = _center()
    ws.row_dimensions[1].height = 32

    # Encabezados
    headers = ["Fecha", "Descripción", "Categoría", "Tipo", "Monto"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font      = _font(bold=True, color=C_PRIMARY, size=11)
        cell.fill      = _fill(C_HEADER)
        cell.alignment = _center()
        cell.border    = _border()
    ws.row_dimensions[2].height = 22

    # Datos
    for i, tx in enumerate(transactions):
        row = i + 3
        is_income = tx[1] == "income"
        bg = C_DARK if i % 2 == 0 else C_ROW_ALT
        amount = float(tx[2]) if is_income else -float(tx[2])
        amount_color = C_INCOME if is_income else C_EXPENSE

        values = [tx[5], tx[4] or "—", tx[3] or "—",
                  "Ingreso" if is_income else "Gasto", amount]
        aligns = [_center(), _left(), _left(), _center(), _center()]

        for col, (val, aln) in enumerate(zip(values, aligns), 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.fill      = _fill(bg)
            cell.border    = _border()
            cell.alignment = aln
            cell.font      = _font(
                color=amount_color if col == 5 else C_WHITE, size=10)
            if col == 5:
                cell.number_format = '$#,##0.00'

    # Fila de totales
    total_row = len(transactions) + 3
    ws.merge_cells(f"A{total_row}:C{total_row}")
    ws[f"A{total_row}"] = "TOTALES"
    ws[f"A{total_row}"].font      = _font(bold=True, color=C_WARNING, size=10)
    ws[f"A{total_row}"].fill      = _fill(C_HEADER)
    ws[f"A{total_row}"].alignment = _center()
    ws[f"A{total_row}"].border    = _border()

    incomes  = sum(float(t[2]) for t in transactions if t[1] == "income")
    expenses = sum(float(t[2]) for t in transactions if t[1] == "expense")

    for col, (val, color) in enumerate(
            [(None, C_WHITE), (incomes, C_INCOME), (-expenses, C_EXPENSE)], 3):
        cell = ws.cell(row=total_row, column=col + 1, value=val)
        cell.font      = _font(bold=True, color=color, size=10)
        cell.fill      = _fill(C_HEADER)
        cell.alignment = _center()
        cell.border    = _border()
        if val is not None:
            cell.number_format = '$#,##0.00'

    # Anchos de columna
    widths = [14, 32, 20, 12, 16]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    # Fondo general
    ws.sheet_properties.tabColor = C_PRIMARY


# ──────────────────────────────────────────────
# Hoja 2 — Resumen e informe IA
# ──────────────────────────────────────────────

def _sheet_summary(wb, data, report_text, projection):
    ws = wb.create_sheet("Resumen general")
    ws.sheet_view.showGridLines = False

    def write(row, col, value, bold=False, color=C_WHITE, size=11,
              fill_color=C_DARK, align=None, num_fmt=None, italic=False,
              merge_to=None):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font      = _font(bold=bold, color=color, size=size, italic=italic)
        cell.fill      = _fill(fill_color)
        cell.alignment = align or _left()
        cell.border    = _border()
        if num_fmt:
            cell.number_format = num_fmt
        if merge_to:
            ws.merge_cells(
                start_row=row, start_column=col,
                end_row=row,   end_column=merge_to)
        return cell

    # ── Título ──
    ws.row_dimensions[1].height = 36
    write(1, 1, f"Reporte Mensual — {data['year_month']}",
          bold=True, color=C_PRIMARY, size=16,
          fill_color=C_DARK, align=_center(), merge_to=8)

    # ── KPI row ──
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 28
    ws.row_dimensions[4].height = 20

    kpis = [
        ("Ingresos del mes", data["income"],   C_INCOME,  "$#,##0.00"),
        ("Gastos del mes",   data["expense"],  C_EXPENSE, "$#,##0.00"),
        ("Neto del mes",     data["balance"],  C_PRIMARY, "$#,##0.00"),
        ("Tasa de ahorro",   data["savings_rate"] / 100, C_WARNING, "0.0%"),
    ]
    col_starts = [1, 3, 5, 7]
    for (label, val, color, fmt), c in zip(kpis, col_starts):
        ws.merge_cells(start_row=2, start_column=c, end_row=2, end_column=c+1)
        ws.merge_cells(start_row=3, start_column=c, end_row=3, end_column=c+1)
        ws.merge_cells(start_row=4, start_column=c, end_row=4, end_column=c+1)
        write(2, c, label,  bold=False, color=C_MUTED,  size=9,
              fill_color=C_HEADER, align=_center())
        write(3, c, val,    bold=True,  color=color,    size=14,
              fill_color=C_HEADER, align=_center(), num_fmt=fmt)
        write(4, c, "",     fill_color=C_HEADER)

    # ── Separador ──
    ws.row_dimensions[5].height = 8
    ws.merge_cells("A5:H5")
    ws["A5"].fill = _fill(C_DARK)

    # ── Gastos por categoría ──
    ws.row_dimensions[6].height = 22
    write(6, 1, "Gastos por Categoría", bold=True, color=C_PRIMARY,
          size=12, fill_color=C_HEADER, align=_center(), merge_to=4)
    write(6, 5, "Mes Anterior", bold=True, color=C_MUTED,
          size=12, fill_color=C_HEADER, align=_center(), merge_to=8)

    cat_headers = ["Categoría", "Monto", "% del total", ""]
    for col, h in enumerate(cat_headers * 2, 1):
        if h:
            write(7, col, h, bold=True, color=C_WHITE,
                  size=10, fill_color=C_HEADER, align=_center())

    total_exp  = data["expense"]  or 1
    prev_total = data["prev_expense"] or 1

    curr_cats = dict(data["categories"])
    prev_cats = dict(data["prev_categories"])
    all_cats  = sorted(set(list(curr_cats.keys()) + list(prev_cats.keys())))

    for i, cat in enumerate(all_cats):
        row = 8 + i
        bg  = C_DARK if i % 2 == 0 else C_ROW_ALT
        ws.row_dimensions[row].height = 18

        curr_amt = curr_cats.get(cat, 0)
        prev_amt = prev_cats.get(cat, 0)
        pct_curr = curr_amt / total_exp  if total_exp  else 0
        pct_prev = prev_amt / prev_total if prev_total else 0

        write(row, 1, cat,       color=C_WHITE,   fill_color=bg, align=_left())
        write(row, 2, curr_amt,  color=C_EXPENSE, fill_color=bg,
              align=_center(), num_fmt="$#,##0.00")
        write(row, 3, pct_curr,  color=C_MUTED,   fill_color=bg,
              align=_center(), num_fmt="0.0%")
        write(row, 4, "",        fill_color=bg)
        write(row, 5, cat,       color=C_MUTED,   fill_color=bg, align=_left())
        write(row, 6, prev_amt,  color=C_MUTED,   fill_color=bg,
              align=_center(), num_fmt="$#,##0.00")
        write(row, 7, pct_prev,  color=C_MUTED,   fill_color=bg,
              align=_center(), num_fmt="0.0%")
        write(row, 8, "",        fill_color=bg)

    next_row = 8 + len(all_cats) + 1

    # ── Gastos próximo mes ──
    ws.row_dimensions[next_row].height = 22
    write(next_row, 1, "Gastos programados próximo mes",
          bold=True, color=C_WARNING, size=12,
          fill_color=C_HEADER, align=_center(), merge_to=8)
    next_row += 1

    up_headers = ["Descripción", "Categoría", "Fecha", "Monto"]
    up_cols    = [1, 3, 5, 7]
    for h, c in zip(up_headers, up_cols):
        write(next_row, c, h, bold=True, color=C_WHITE,
              size=10, fill_color=C_HEADER, align=_center(), merge_to=c+1)
    next_row += 1

    if data["upcoming_payments"]:
        for i, (desc, amt, date, cat) in enumerate(data["upcoming_payments"]):
            bg = C_DARK if i % 2 == 0 else C_ROW_ALT
            ws.row_dimensions[next_row].height = 18
            write(next_row, 1, desc, color=C_WHITE,   fill_color=bg, merge_to=2)
            write(next_row, 3, cat,  color=C_MUTED,   fill_color=bg, merge_to=4)
            write(next_row, 5, date, color=C_MUTED,   fill_color=bg,
                  align=_center(), merge_to=6)
            write(next_row, 7, amt,  color=C_EXPENSE, fill_color=bg,
                  align=_center(), num_fmt="$#,##0.00", merge_to=8)
            next_row += 1
    else:
        ws.merge_cells(
            start_row=next_row, start_column=1,
            end_row=next_row,   end_column=8)
        write(next_row, 1, "Sin gastos programados para el próximo mes.",
              color=C_MUTED, fill_color=C_DARK,
              align=_center(), italic=True)
        next_row += 1

    next_row += 1

    # ── Informe IA ──
    ws.row_dimensions[next_row].height = 22
    write(next_row, 1, "Informe generado por IA",
          bold=True, color=C_PRIMARY, size=12,
          fill_color=C_HEADER, align=_center(), merge_to=8)
    next_row += 1

    if report_text:
        for line in report_text.split("\n"):
            clean = line.strip().lstrip("#").strip()
            if not clean:
                ws.row_dimensions[next_row].height = 8
                write(next_row, 1, "", fill_color=C_DARK, merge_to=8)
            else:
                is_heading = line.startswith("#")
                ws.row_dimensions[next_row].height = 20 if is_heading else 16
                ws.merge_cells(
                    start_row=next_row, start_column=1,
                    end_row=next_row,   end_column=8)
                cell = ws.cell(row=next_row, column=1, value=clean)
                cell.font      = _font(bold=is_heading,
                                       color=C_WARNING if is_heading else C_WHITE,
                                       size=11 if is_heading else 10)
                cell.fill      = _fill(C_HEADER if is_heading else C_DARK)
                cell.alignment = Alignment(horizontal="left", vertical="center",
                                           wrap_text=True)
                cell.border    = _border()
            next_row += 1
    else:
        write(next_row, 1,
              "Generá el reporte desde la pestaña 'Reporte IA' para ver el informe aquí.",
              color=C_MUTED, fill_color=C_DARK,
              align=_center(), italic=True, merge_to=8)

    # Anchos columnas
    for col, w in enumerate([22, 4, 22, 4, 14, 4, 16, 4], 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.sheet_properties.tabColor = C_WARNING


# ──────────────────────────────────────────────
# Función principal
# ──────────────────────────────────────────────

def generate_excel_report(transactions, data, report_text=None, projection=None) -> bytes:
    """
    Genera el reporte en memoria y devuelve bytes del .xlsx.
    transactions: lista de tuplas de get_transactions()
    data:         dict de get_monthly_detail()
    report_text:  str del reporte IA (opcional)
    projection:   lista de get_cash_flow_projection() (opcional, reservado)
    """
    wb = openpyxl.Workbook()
    # Eliminar hoja por defecto
    wb.remove(wb.active)

    _sheet_transactions(wb, transactions, data["year_month"])
    _sheet_summary(wb, data, report_text, projection)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
