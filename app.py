import os, json, sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from nlp_processor import extractor
from datetime import datetime
from database import init_db

app = Flask(__name__)

# 持久化图片目录
UPLOAD_FOLDER = '/data/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 容器启动时初始化环境
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_db()

def get_db():
    conn = sqlite3.connect('/data/recipes.db')
    conn.row_factory = sqlite3.Row
    return conn

def to_minutes(val, unit):
    val = int(val) if str(val).isdigit() else 0
    if unit == "小时": return val * 60
    if unit == "天": return val * 1440
    return val

# 自定义路由：从 /data/uploads 提供图片服务
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    search = request.args.get('search', '')
    cat = request.args.get('category', '')
    conn = get_db()
    
    query = "SELECT * FROM recipes WHERE (title LIKE ? OR ingredients LIKE ?)"
    params = [f'%{search}%', f'%{search}%']
    if cat:
        query += " AND category LIKE ?"
        params.append(f'%"{cat}"%')
        
    recipes = conn.execute(query + " ORDER BY created_at DESC", params).fetchall()
    
    processed = []
    for r in recipes:
        d = dict(r)
        d['category'] = json.loads(d['category'])
        d['ingredients'] = json.loads(d['ingredients'])
        d['steps'] = json.loads(d['steps'])
        processed.append(d)
    conn.close()
    return render_template('index.html', recipes=processed, search=search)

@app.route('/api/analyze', methods=['POST'])
def analyze_steps():
    data = request.json
    text = " ".join(data.get('steps', []))
    ingredients = extractor.extract(text)
    return jsonify({"ingredients": ingredients})

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        title = request.form['title']
        categories = request.form.getlist('categories[]')
        
        # 处理新建类别
        new_category = request.form.get('new_category', '').strip()
        if new_category:
            extra_tags = [t.strip() for t in new_category.replace('，', ',').split(',') if t.strip()]
            categories.extend(extra_tags)
        categories = list(set(categories)) # 去重
        
        steps = [s for s in request.form.getlist('steps[]') if s.strip()]
        ingredients = request.form.getlist('ingredients[]')
        note = request.form.get('note', '')
        
        d_val = request.form.get('duration_val', '0')
        d_unit = request.form.get('duration_unit', '分钟')
        
        # 处理图片
        file = request.files['image']
        if file and file.filename:
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = ""
        
        conn = get_db()
        conn.execute('''INSERT INTO recipes 
            (title, category, ingredients, steps, duration_display, duration_minutes, note, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (title, json.dumps(categories, ensure_ascii=False), 
             json.dumps(ingredients, ensure_ascii=False),
             json.dumps(steps, ensure_ascii=False),
             f"{d_val} {d_unit}", to_minutes(d_val, d_unit),
             note, filename))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()
    recipe = conn.execute("SELECT image_path FROM recipes WHERE id=?", (id,)).fetchone()
    if recipe and recipe['image_path']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], recipe['image_path'])
        if os.path.exists(path): os.remove(path)
    conn.execute("DELETE FROM recipes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # 0.0.0.0 确保 Docker 外部可以访问
    app.run(host='0.0.0.0', port=5000)