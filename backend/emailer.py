import smtplib
import os
import base64
import plotly.graph_objects as go
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from database import get_db

RECIPIENTS = ['victorsanabia@gmail.com', 'dominique.guidry@gmail.com']
EXCLUDE = ('Transfer', 'Bank Fees')

def chart_to_base64(fig):
    img_bytes = fig.to_image(format='png', width=600, height=320, scale=2)
    return base64.b64encode(img_bytes).decode('utf-8')

def make_bar_chart(by_category):
    cats = [r['category'] for r in by_category]
    vals = [r['total'] for r in by_category]
    colors = ['#e74c3c' if v > 1000 else '#3498db' for v in vals]
    fig = go.Figure(go.Bar(
        x=cats, y=vals,
        marker_color=colors,
        text=[f'${v:,.0f}' for v in vals],
        textposition='outside',
    ))
    fig.update_layout(
        margin=dict(t=20, b=60, l=60, r=20),
        paper_bgcolor='white', plot_bgcolor='white',
        yaxis=dict(tickprefix='$', gridcolor='#f0f0f0'),
        font=dict(family='Arial', size=11),
        showlegend=False,
    )
    return chart_to_base64(fig)

def make_sankey_chart(by_category, income, total_spent):
    cat_names = [r['category'] for r in by_category]
    expenses = {r['category']: r['total'] for r in by_category}
    saved = max(0, income - total_spent)
    deficit = max(0, total_spent - income)
    outcome_label = 'Savings' if saved > 0 else 'Deficit'
    nodes = ['Income'] + cat_names + [outcome_label]
    n_cats = len(cat_names)
    node_x = [0.01] + [0.5] * n_cats + [0.99]
    node_y = [0.5] + [round(0.05 + i * (0.9 / max(n_cats - 1, 1)), 3) for i in range(n_cats)] + [0.5]

    sources, targets, values = [], [], []
    for i, cat in enumerate(cat_names):
        sources.append(0); targets.append(i + 1); values.append(expenses[cat])
    outcome_amount = saved if saved > 0 else deficit
    for i, cat in enumerate(cat_names):
        sources.append(i + 1); targets.append(len(nodes) - 1)
        values.append(expenses[cat] / total_spent * outcome_amount if total_spent > 0 else 0)

    node_colors = []
    for n in nodes:
        if n == 'Income': node_colors.append('#27ae60')
        elif n == 'Savings': node_colors.append('#2ecc71')
        elif n == 'Deficit': node_colors.append('#e74c3c')
        else: node_colors.append('#3498db')

    fig = go.Figure(go.Sankey(
        arrangement='snap',
        node=dict(pad=12, thickness=20, label=nodes, color=node_colors, x=node_x, y=node_y),
        link=dict(source=sources, target=targets, value=values,
                  color=['rgba(52,152,219,0.2)'] * len(values))
    ))
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='white', font=dict(size=11))
    return chart_to_base64(fig)

def make_trend_chart(monthly_trend):
    months = [t['month'] for t in monthly_trend]
    # Format as "Apr 2026"
    def fmt_month(m):
        from datetime import datetime
        return datetime.strptime(m, '%Y-%m').strftime('%b %Y')
    labels = [fmt_month(m) for m in months]
    income = [t['income'] for t in monthly_trend]
    spent = [t['spent'] for t in monthly_trend]
    net = [i - s for i, s in zip(income, spent)]

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Income', x=labels, y=income, marker_color='#27ae60'))
    fig.add_trace(go.Bar(name='Spending', x=labels, y=spent, marker_color='#e74c3c'))
    fig.add_trace(go.Scatter(
        name='Net', x=labels, y=net,
        mode='lines+markers',
        line=dict(color='#2980b9', width=2),
        marker=dict(size=7),
        yaxis='y2',
    ))
    fig.update_layout(
        barmode='group',
        margin=dict(t=20, b=50, l=70, r=70),
        paper_bgcolor='white', plot_bgcolor='white',
        yaxis=dict(tickprefix='$', gridcolor='#f0f0f0'),
        yaxis2=dict(tickprefix='$', overlaying='y', side='right'),
        legend=dict(orientation='h', y=-0.25),
        font=dict(family='Arial', size=11),
    )
    return chart_to_base64(fig)

def build_report_html(month: str) -> str:
    conn = get_db()
    exclude_sql = ','.join(f"'{e}'" for e in EXCLUDE)
    rows = conn.execute(
        f"SELECT category, SUM(amount) as total FROM transactions WHERE month=? AND amount < 0 AND category NOT IN ({exclude_sql}) GROUP BY category ORDER BY total ASC",
        (month,)
    ).fetchall()
    income_row = conn.execute(
        f"SELECT SUM(amount) as total FROM transactions WHERE month=? AND amount > 0 AND category NOT IN ({exclude_sql})",
        (month,)
    ).fetchone()
    monthly_trend = conn.execute(
        f"""SELECT month,
            SUM(CASE WHEN amount < 0 AND category NOT IN ({exclude_sql}) THEN ABS(amount) ELSE 0 END) as spent,
            SUM(CASE WHEN amount > 0 AND category NOT IN ({exclude_sql}) THEN amount ELSE 0 END) as income
            FROM transactions GROUP BY month ORDER BY month DESC LIMIT 3""",
    ).fetchall()
    monthly_trend = list(reversed(monthly_trend))
    goals = conn.execute("SELECT * FROM savings_goals ORDER BY id").fetchall()
    conn.close()

    by_category = [{'category': r['category'], 'total': abs(r['total'])} for r in rows]
    by_category.sort(key=lambda x: -x['total'])

    total_spent = sum(r['total'] for r in by_category)
    total_income = income_row['total'] or 0
    net = total_income - total_spent
    saved = max(0, net)
    deficit = max(0, -net)

    # Generate charts
    sankey_b64 = make_sankey_chart(by_category, total_income, total_spent) if by_category else None
    bar_b64 = make_bar_chart(by_category) if by_category else None
    trend_b64 = make_trend_chart([dict(r) for r in monthly_trend]) if monthly_trend else None

    from datetime import datetime
    month_label = datetime.strptime(month, '%Y-%m').strftime('%B %Y')

    category_rows = ''.join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #f0f0f0'>{r['category']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#e74c3c;font-weight:600'>${r['total']:,.2f}</td></tr>"
        for r in by_category
    )

    goals_rows = ''.join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #f0f0f0'>{g['name']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0'>"
        f"<div style='background:#eee;border-radius:99px;height:8px;width:150px;display:inline-block;vertical-align:middle'>"
        f"<div style='background:#27ae60;height:8px;border-radius:99px;width:{min(100, g['current_amount']/g['target_amount']*100) if g['target_amount'] else 0:.0f}%'></div></div>"
        f"&nbsp; ${g['current_amount']:,.0f} / ${g['target_amount']:,.0f}</td></tr>"
        for g in goals
    ) if goals else "<tr><td colspan='2' style='padding:12px;color:#aaa'>No goals set yet.</td></tr>"

    net_color = '#27ae60' if net >= 0 else '#e74c3c'
    net_label = f'Saved: ${saved:,.2f}' if net >= 0 else f'Deficit: ${deficit:,.2f}'

    sankey_img = f'<img src="data:image/png;base64,{sankey_b64}" style="width:100%;max-width:600px;display:block;margin:0 auto" />' if sankey_b64 else ''
    bar_img = f'<img src="data:image/png;base64,{bar_b64}" style="width:100%;max-width:600px;display:block;margin:0 auto" />' if bar_b64 else ''
    trend_img = f'<img src="data:image/png;base64,{trend_b64}" style="width:100%;max-width:600px;display:block;margin:0 auto" />' if trend_b64 else ''

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#333;background:#f4f6f9;padding:20px">
      <div style="background:#2c3e50;color:white;padding:24px 28px;border-radius:10px 10px 0 0">
        <h2 style="margin:0;font-size:20px">💰 Budget Report — {month_label}</h2>
        <p style="margin:4px 0 0;opacity:.7;font-size:13px">Victor &amp; Dominique</p>
      </div>

      <div style="background:white;padding:24px 28px">
        <div style="display:flex;gap:12px;margin-bottom:24px">
          <div style="flex:1;background:#eafaf1;border-radius:8px;padding:14px;text-align:center">
            <div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px">Income</div>
            <div style="font-size:22px;font-weight:700;color:#27ae60">${total_income:,.2f}</div>
          </div>
          <div style="flex:1;background:#fdf2f2;border-radius:8px;padding:14px;text-align:center">
            <div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px">Spent</div>
            <div style="font-size:22px;font-weight:700;color:#e74c3c">${total_spent:,.2f}</div>
          </div>
          <div style="flex:1;background:#{'eafaf1' if net >= 0 else 'fdf2f2'};border-radius:8px;padding:14px;text-align:center">
            <div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px">{'Saved' if net >= 0 else 'Deficit'}</div>
            <div style="font-size:22px;font-weight:700;color:{net_color}">${abs(net):,.2f}</div>
          </div>
        </div>

        <h3 style="font-size:14px;margin:0 0 12px;color:#2c3e50">Spending Flow</h3>
        {sankey_img}

        <h3 style="font-size:14px;margin:24px 0 12px;color:#2c3e50">Spending by Category</h3>
        {bar_img}

        <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:13px">
          <tr style="background:#f8f9fa">
            <th style="text-align:left;padding:8px 12px;color:#666;font-weight:600;font-size:11px;text-transform:uppercase">Category</th>
            <th style="text-align:right;padding:8px 12px;color:#666;font-weight:600;font-size:11px;text-transform:uppercase">Amount</th>
          </tr>
          {category_rows}
        </table>

        <h3 style="font-size:14px;margin:24px 0 12px;color:#2c3e50">Income vs Spending — Last 3 Months</h3>
        {trend_img}

        {'<h3 style="font-size:14px;margin:24px 0 12px;color:#2c3e50">Savings Goals</h3><table style="width:100%;border-collapse:collapse;font-size:13px"><tr style="background:#f8f9fa"><th style="text-align:left;padding:8px 12px;color:#666;font-size:11px;text-transform:uppercase">Goal</th><th style="padding:8px 12px;color:#666;font-size:11px;text-transform:uppercase">Progress</th></tr>' + goals_rows + '</table>' if goals else ''}

        <p style="margin-top:28px;font-size:11px;color:#aaa;border-top:1px solid #eee;padding-top:16px">
          Sent automatically by your Budget Tracker · Victor &amp; Dominique
        </p>
      </div>
    </body></html>
    """

def send_monthly_report(month: str, smtp_user: str, smtp_pass: str):
    html = build_report_html(month)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'💰 Budget Report — {month}'
    msg['From'] = smtp_user
    msg['To'] = ', '.join(RECIPIENTS)
    msg.attach(MIMEText(html, 'html'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, RECIPIENTS, msg.as_string())
