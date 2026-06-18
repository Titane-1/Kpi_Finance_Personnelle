from flask import Flask, render_template, request, jsonify, Response
import sqlite3
import csv
import io

app = Flask(__name__)
DB_FILE = 'portage_os.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS monthly_stats (
                    month_year TEXT PRIMARY KEY,
                    ca REAL, culture REAL, pee REAL, super_net REAL, pouvoir_achat_total REAL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month_year TEXT, category TEXT, name TEXT, amount REAL
                )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save_simu', methods=['POST'])
def save_simu():
    try:
        data = request.json
        month_year = data.get('month_year')
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Sauvegarde uniquement la simulation. REPLACE INTO est 100% compatible.
        c.execute('''REPLACE INTO monthly_stats (month_year, ca, culture, pee, super_net, pouvoir_achat_total) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                  (month_year, data.get('ca',0), data.get('culture',0), data.get('pee',0), data.get('super_net',0), data.get('pouvoir_achat_total',0)))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Simulateur de {month_year} sauvegardé !"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/save_budget', methods=['POST'])
def save_budget():
    try:
        data = request.json
        month_year = data.get('month_year')
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Crée une ligne vide dans la simulation si elle n'existe pas pour lier les bases de données
        c.execute('INSERT OR IGNORE INTO monthly_stats (month_year, ca, culture, pee, super_net, pouvoir_achat_total) VALUES (?, 0, 0, 0, 0, 0)', (month_year,))
        
        # Remplace uniquement les dépenses
        c.execute('DELETE FROM expenses WHERE month_year = ?', (month_year,))
        for exp in data.get('expenses', []):
            if exp['amount'] > 0: # Ne sauvegarde que si la case n'est pas vide
                c.execute('INSERT INTO expenses (month_year, category, name, amount) VALUES (?, ?, ?, ?)',
                          (month_year, exp['category'], exp['name'], exp['amount']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Dépenses de {month_year} sauvegardées !"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get_month/<month_year>', methods=['GET'])
def get_month(month_year):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM expenses WHERE month_year = ?', (month_year,))
    expenses = c.fetchall()
    conn.close()
    return jsonify({"expenses": [dict(e) for e in expenses]})

@app.route('/api/get_history', methods=['GET'])
def get_history():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT m.month_year, m.ca, m.super_net, m.pouvoir_achat_total, m.pee, 
               COALESCE(SUM(CASE WHEN e.category='investissement' THEN e.amount ELSE 0 END), 0) as total_pea,
               COALESCE(SUM(CASE WHEN e.category='depense' THEN e.amount ELSE 0 END), 0) as total_depenses
        FROM monthly_stats m
        LEFT JOIN expenses e ON m.month_year = e.month_year
        GROUP BY m.month_year ORDER BY m.month_year DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in rows])

@app.route('/api/export', methods=['GET'])
def export_csv():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT m.month_year, m.ca, m.super_net, m.pouvoir_achat_total, m.pee, 
                        COALESCE(SUM(CASE WHEN e.category='investissement' THEN e.amount ELSE 0 END), 0) as total_pea,
                        COALESCE(SUM(CASE WHEN e.category='depense' THEN e.amount ELSE 0 END), 0) as total_depenses
                 FROM monthly_stats m
                 LEFT JOIN expenses e ON m.month_year = e.month_year
                 GROUP BY m.month_year ORDER BY m.month_year DESC''')
    rows = c.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Mois', 'Revenus (CA/Brut)', 'Cash Super Net', 'Pouvoir Achat Total', 'Investi PEE', 'Investi PEA', 'Dépenses Courantes'])
    writer.writerows(rows)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=export_portage_os.csv"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')