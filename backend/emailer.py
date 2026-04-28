import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from database import get_db

RECIPIENTS = ['victorsanabia@gmail.com', 'dominique.guidry@gmail.com']

def build_report_html(month: str) -> str:
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM transactions WHERE month=? AND amount < 0 GROUP BY category ORDER BY total ASC",
        (month,)
    ).fetchall()
    income_row = conn.execute(
        "SELECT SUM(amount) as total FROM transactions WHERE month=? AND amount > 0",
        (month,)
    ).fetchone()
    goals = conn.execute("SELECT * FROM savings_goals").fetchall()
    conn.close()

    total_spent = sum(abs(r['total']) for r in rows)
    total_income = income_row['total'] or 0

    category_rows = ''.join(
        f"<tr><td>{r['category']}</td><td style='text-align:right;color:#e74c3c'>${abs(r['total']):.2f}</td></tr>"
        for r in rows
    )

    goals_rows = ''.join(
        f"<tr><td>{g['name']}</td><td style='text-align:right'>${g['current_amount']:.2f} / ${g['target_amount']:.2f}</td><td style='text-align:right'>{min(100, g['current_amount']/g['target_amount']*100):.0f}%</td></tr>"
        for g in goals
    ) if goals else '<tr><td colspan="3">No goals set yet.</td></tr>'

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#333">
      <h2 style="background:#2c3e50;color:white;padding:20px;margin:0">Budget Report — {month}</h2>
      <div style="padding:20px">
        <div style="display:flex;gap:20px;margin-bottom:20px">
          <div style="flex:1;background:#eafaf1;border-radius:8px;padding:15px;text-align:center">
            <div style="font-size:12px;color:#666">Total Income</div>
            <div style="font-size:24px;font-weight:bold;color:#27ae60">${total_income:.2f}</div>
          </div>
          <div style="flex:1;background:#fdf2f2;border-radius:8px;padding:15px;text-align:center">
            <div style="font-size:12px;color:#666">Total Spent</div>
            <div style="font-size:24px;font-weight:bold;color:#e74c3c">${total_spent:.2f}</div>
          </div>
          <div style="flex:1;background:#eaf4fb;border-radius:8px;padding:15px;text-align:center">
            <div style="font-size:12px;color:#666">Net</div>
            <div style="font-size:24px;font-weight:bold;color:#2980b9">${total_income - total_spent:.2f}</div>
          </div>
        </div>
        <h3>Spending by Category</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr style="background:#f5f5f5"><th style="text-align:left;padding:8px">Category</th><th style="text-align:right;padding:8px">Amount</th></tr>
          {category_rows}
        </table>
        <h3 style="margin-top:30px">Savings Goals</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr style="background:#f5f5f5"><th style="text-align:left;padding:8px">Goal</th><th style="text-align:right;padding:8px">Progress</th><th style="text-align:right;padding:8px">%</th></tr>
          {goals_rows}
        </table>
        <p style="margin-top:30px;font-size:12px;color:#999">Sent by Budget Tracker · Victor & Dominique</p>
      </div>
    </body></html>
    """

def send_monthly_report(month: str, smtp_user: str, smtp_pass: str):
    html = build_report_html(month)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Budget Report — {month}'
    msg['From'] = smtp_user
    msg['To'] = ', '.join(RECIPIENTS)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, RECIPIENTS, msg.as_string())
