import sqlite3
import os

# 强制指向 Docker 提供的持久化目录
DB_PATH = '/data/recipes.db'

def init_db():
    # 确保目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,          -- JSON 数组
            ingredients TEXT,       -- JSON 数组
            steps TEXT,             -- JSON 数组
            duration_display TEXT,  -- 展示用时，如 "30 分钟"
            duration_minutes INTEGER, -- 计算用时，如 30
            note TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 动态黑名单表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("数据库初始化/检查完毕。")

if __name__ == "__main__":
    init_db()