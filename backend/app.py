import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from database import init_db, get_db
from csv_parser import parse_usbank_csv
from categorizer import categorize
from emailer import send_monthly_report

load_dotenv()

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

init_db()

# ── Serve frontend ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

# ── Transactions ────────────────────────────────────────────────────────────

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    source = request.form.get('source', 'checking')
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    transactions = parse_usbank_csv(file.read(), source)

    conn = get_db()
    inserted = 0
    for t in transactions:
        conn.execute(
            "INSERT INTO transactions (date, description, amount, category, source, month) VALUES (?,?,?,?,?,?)",
            (t['date'], t['description'], t['amount'], t['category'], t['source'], t['month'])
        )
        inserted += 1
    conn.commit()
    conn.close()
    return jsonify({'inserted': inserted})

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    month = request.args.get('month')
    conn = get_db()
    if month:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE month=? ORDER BY date DESC", (month,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM transactions ORDER BY date DESC LIMIT 200").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/recategorize', methods=['POST'])
def recategorize_all():
    conn = get_db()
    rows = conn.execute("SELECT id, description FROM transactions").fetchall()
    for row in rows:
        new_cat = categorize(row['description'])
        conn.execute("UPDATE transactions SET category=? WHERE id=?", (new_cat, row['id']))
    conn.commit()
    conn.close()
    return jsonify({'updated': len(rows)})

@app.route('/api/transactions/<int:tid>', methods=['PATCH'])
def update_transaction(tid):
    data = request.get_json()
    category = data.get('category')
    conn = get_db()
    conn.execute("UPDATE transactions SET category=? WHERE id=?", (category, tid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/transactions/<int:tid>', methods=['DELETE'])
def delete_transaction(tid):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── Summary & Sankey ────────────────────────────────────────────────────────

@app.route('/api/summary', methods=['GET'])
def summary():
    month = request.args.get('month')
    conn = get_db()

    # Exclude Transfer + Bank Fees from spending so credit card payments don't double-count
    EXCLUDE = ('Transfer', 'Bank Fees')
    exclude_placeholders = ','.join('?' * len(EXCLUDE))

    if month:
        by_category = conn.execute(
            f"SELECT category, SUM(amount) as total FROM transactions WHERE month=? AND category NOT IN ({exclude_placeholders}) GROUP BY category",
            (month, *EXCLUDE)
        ).fetchall()
        monthly = [{'month': month, 'spent': sum(abs(r['total']) for r in by_category if r['total'] < 0),
                    'income': sum(r['total'] for r in by_category if r['total'] > 0)}]
    else:
        by_category = conn.execute(
            f"SELECT category, SUM(amount) as total FROM transactions WHERE category NOT IN ({exclude_placeholders}) GROUP BY category",
            EXCLUDE
        ).fetchall()
        monthly = conn.execute(
            f"""SELECT month,
               SUM(CASE WHEN amount < 0 AND category NOT IN ({exclude_placeholders}) THEN ABS(amount) ELSE 0 END) as spent,
               SUM(CASE WHEN amount > 0 AND category NOT IN ({exclude_placeholders}) THEN amount ELSE 0 END) as income
               FROM transactions GROUP BY month ORDER BY month""",
            (*EXCLUDE, *EXCLUDE)
        ).fetchall()

    conn.close()

    expenses = {r['category']: abs(r['total']) for r in by_category if r['total'] < 0}
    income = sum(r['total'] for r in by_category if r['total'] > 0)
    total_spent = sum(expenses.values())
    saved = max(0, income - total_spent)

    # 3-level Sankey: Income (left) → Categories (middle) → Savings/Deficit (right)
    deficit = max(0, total_spent - income)
    cat_names = list(expenses.keys())
    n_cats = len(cat_names)

    # Node order: Income, ...categories..., Savings or Deficit
    sankey_nodes = ['Income'] + cat_names
    outcome_label = 'Savings' if saved > 0 else 'Deficit'
    sankey_nodes.append(outcome_label)

    income_idx = 0
    outcome_idx = len(sankey_nodes) - 1

    sankey_sources = []
    sankey_targets = []
    sankey_values = []

    # Income → each category (full expense amount)
    for i, cat in enumerate(cat_names):
        cat_idx = i + 1
        sankey_sources.append(income_idx)
        sankey_targets.append(cat_idx)
        sankey_values.append(expenses[cat])

    # Each category → Savings (proportional share) or → Deficit (proportional share)
    outcome_amount = saved if saved > 0 else deficit
    for i, cat in enumerate(cat_names):
        cat_idx = i + 1
        share = expenses[cat] / total_spent * outcome_amount if total_spent > 0 else 0
        sankey_sources.append(cat_idx)
        sankey_targets.append(outcome_idx)
        sankey_values.append(share)

    # Node x/y positions: Income left, categories middle, outcome right
    n_nodes = len(sankey_nodes)
    node_x = [0.01] + [0.5] * n_cats + [0.99]
    # Spread categories evenly in y
    cat_ys = [round(0.05 + i * (0.9 / max(n_cats - 1, 1)), 3) for i in range(n_cats)]
    node_y = [0.5] + cat_ys + [0.5]

    node_colors = []
    for node in sankey_nodes:
        if node == 'Income':
            node_colors.append('#27ae60')
        elif node == 'Savings':
            node_colors.append('#2ecc71')
        elif node == 'Deficit':
            node_colors.append('#e74c3c')
        else:
            node_colors.append('#3498db')

    return jsonify({
        'income': income,
        'total_spent': total_spent,
        'saved': saved,
        'by_category': [{'category': k, 'total': v} for k, v in sorted(expenses.items(), key=lambda x: -x[1])],
        'monthly_trend': [dict(r) for r in monthly],
        'sankey': {
            'nodes': sankey_nodes,
            'sources': sankey_sources,
            'targets': sankey_targets,
            'values': sankey_values,
            'node_colors': node_colors,
            'node_x': node_x,
            'node_y': node_y,
        }
    })

@app.route('/api/transactions/by-category', methods=['GET'])
def transactions_by_category():
    category = request.args.get('category')
    month = request.args.get('month')
    conn = get_db()
    if month:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE category=? AND month=? ORDER BY date DESC",
            (category, month)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE category=? ORDER BY date DESC",
            (category,)
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/months', methods=['GET'])
def get_months():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT month FROM transactions ORDER BY month DESC").fetchall()
    conn.close()
    return jsonify([r['month'] for r in rows])

# ── Savings Goals ───────────────────────────────────────────────────────────

@app.route('/api/goals', methods=['GET'])
def get_goals():
    conn = get_db()
    rows = conn.execute("SELECT * FROM savings_goals ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/goals', methods=['POST'])
def create_goal():
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "INSERT INTO savings_goals (name, target_amount, current_amount, deadline) VALUES (?,?,?,?)",
        (data['name'], data['target_amount'], data.get('current_amount', 0), data.get('deadline'))
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/goals/<int:gid>', methods=['PATCH'])
def update_goal(gid):
    data = request.get_json()
    conn = get_db()
    fields = ', '.join(f"{k}=?" for k in data)
    conn.execute(f"UPDATE savings_goals SET {fields} WHERE id=?", list(data.values()) + [gid])
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/goals/<int:gid>', methods=['DELETE'])
def delete_goal(gid):
    conn = get_db()
    conn.execute("DELETE FROM savings_goals WHERE id=?", (gid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── Email ────────────────────────────────────────────────────────────────────

@app.route('/api/send-report', methods=['POST'])
def send_report():
    data = request.get_json()
    month = data.get('month', datetime.now().strftime('%Y-%m'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    if not smtp_user or not smtp_pass:
        return jsonify({'error': 'Email not configured. Add SMTP_USER and SMTP_PASS to .env'}), 400
    try:
        send_monthly_report(month, smtp_user, smtp_pass)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/email-config', methods=['POST'])
def save_email_config():
    data = request.get_json()
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    with open(env_path, 'w') as f:
        f.write(f"SMTP_USER={data['smtp_user']}\n")
        f.write(f"SMTP_PASS={data['smtp_pass']}\n")
    load_dotenv(override=True)
    return jsonify({'ok': True})

# ── Scheduler: send on 1st of each month ─────────────────────────────────

def scheduled_send():
    month = datetime.now().strftime('%Y-%m')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    if smtp_user and smtp_pass:
        prev_month = (datetime.now().replace(day=1) - __import__('datetime').timedelta(days=1)).strftime('%Y-%m')
        send_monthly_report(prev_month, smtp_user, smtp_pass)

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_send, 'cron', day=1, hour=8, minute=0)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
