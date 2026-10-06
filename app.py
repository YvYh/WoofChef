import os, json, sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from nlp_processor import extractor
from datetime import datetime
from database import init_db

app = Flask(__name__)

# 持久化图片目录
UPLOAD_FOLDER = '/data/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

# 路由：提供用户上传的图片
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 新增路由：提供 UI 图标 (1.png, 2.png)
@app.route('/image/<filename>')
def serve_ui_image(filename):
    # 这里指向你项目根目录下的 image 文件夹
    return send_from_directory('image', filename)

@app.route('/')
def index():
    search = request.args.get('search', '').strip()
    selected_cats = request.args.getlist('categories') # 获取多选分类
    selected_ings = request.args.getlist('ingredients') # 获取多选食材
    duration_filter = request.args.get('duration', 'all') # 获取时长单选

    conn = get_db()
    
    # 1. 提取所有供下拉框使用的去重分类和食材
    all_data = conn.execute("SELECT category, ingredients FROM recipes").fetchall()
    all_categories = set()
    all_ingredients = set()
    for row in all_data:
        cats = json.loads(row['category']) if row['category'] else []
        ings = json.loads(row['ingredients']) if row['ingredients'] else []
        all_categories.update(cats)
        all_ingredients.update(ings)

    # 2. 构建多维筛选 SQL
    query = "SELECT * FROM recipes WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE ? OR note LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])

    if selected_cats:
        # 用户勾选了任意分类，采用 OR 逻辑
        cat_conditions = " OR ".join(["category LIKE ?" for _ in selected_cats])
        query += f" AND ({cat_conditions})"
        params.extend([f'%"{c}"%' for c in selected_cats])

    if selected_ings:
        # 用户勾选了任意食材，采用 OR 逻辑
        ing_conditions = " OR ".join(["ingredients LIKE ?" for _ in selected_ings])
        query += f" AND ({ing_conditions})"
        params.extend([f'%"{i}"%' for i in selected_ings])

    if duration_filter != 'all':
        if duration_filter == 'under_30':
            query += " AND duration_minutes <= 30"
        elif duration_filter == 'under_60':
            query += " AND duration_minutes <= 60"
        elif duration_filter == 'over_60':
            query += " AND duration_minutes > 60"
        
    query += " ORDER BY created_at DESC"
    recipes = conn.execute(query, params).fetchall()
    
    processed = []
    for r in recipes:
        d = dict(r)
        d['category'] = json.loads(d['category']) if d['category'] else []
        d['ingredients'] = json.loads(d['ingredients']) if d['ingredients'] else []
        d['steps'] = json.loads(d['steps']) if d['steps'] else []
        processed.append(d)
        
    conn.close()
    
    return render_template('index.html', 
                           recipes=processed, 
                           search=search,
                           all_categories=sorted(list(all_categories)),
                           all_ingredients=sorted(list(all_ingredients)),
                           selected_cats=selected_cats,
                           selected_ings=selected_ings,
                           duration_filter=duration_filter)

@app.route('/recipe/<int:id>')
def recipe_detail(id):
    conn = get_db()
    recipe = conn.execute("SELECT * FROM recipes WHERE id=?", (id,)).fetchone()
    conn.close()

    if recipe is None:
        return "菜谱不存在或已被删除", 404

    # 将数据库读取的数据转为字典并解析 JSON
    d = dict(recipe)
    d['category'] = json.loads(d['category']) if d['category'] else []
    d['ingredients'] = json.loads(d['ingredients']) if d['ingredients'] else []
    d['steps'] = json.loads(d['steps']) if d['steps'] else []

    return render_template('detail.html', recipe=d)

# 获取动态白名单（所有已存在的食材）和黑名单
def get_dynamic_lists():
    conn = get_db()
    # 1. 获取白名单（解析所有菜谱中的食材）
    recipes = conn.execute("SELECT ingredients FROM recipes WHERE ingredients IS NOT NULL").fetchall()
    whitelist = set()
    for r in recipes:
        ings = json.loads(r['ingredients']) if r['ingredients'] else []
        whitelist.update(ings)
        
    # 2. 获取黑名单
    black_rows = conn.execute("SELECT word FROM blacklist").fetchall()
    blacklist = {row['word'] for row in black_rows}
    
    conn.close()
    return whitelist, blacklist

@app.route('/api/analyze', methods=['POST'])
def analyze_steps():
    data = request.json
    text = " ".join(data.get('steps', []))
    # 每次分析前，获取最新的黑白名单
    dynamic_whitelist, dynamic_blacklist = get_dynamic_lists()
    ingredients = extractor.extract(text, dynamic_whitelist, dynamic_blacklist)
    return jsonify({"ingredients": ingredients})

# 前端点击删除时，将词加入黑名单的 API
@app.route('/api/blacklist', methods=['POST'])
def add_to_blacklist():
    word = request.json.get('word', '').strip()
    if word:
        conn = get_db()
        # 使用 OR IGNORE 防止重复插入报错
        conn.execute("INSERT OR IGNORE INTO blacklist (word) VALUES (?)", (word,))
        conn.commit()
        conn.close()
    return jsonify({"status": "success"})


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
        # 强制将所列食材其黑名单中踢出，防止误写入白名单
        for ing in ingredients:
            conn.execute("DELETE FROM blacklist WHERE word=?", (ing,))
        # 存储菜谱
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
    app.run(debug=True, host='0.0.0.0', port=5000)