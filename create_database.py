import sqlite3

def create_database():
    # Xóa tệp cơ sở dữ liệu cũ nếu có
    import os
    if os.path.exists('database.db'):
        os.remove('database.db')

    # Kết nối đến cơ sở dữ liệu
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Tạo bảng user
    c.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            finances TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


    # Cam kết và đóng kết nối
    conn.commit()
    conn.close()

# Gọi hàm để tạo cơ sở dữ liệu và bảng
create_database()
