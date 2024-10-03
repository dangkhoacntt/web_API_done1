import sqlite3

def convert_finances_column():
    # Kết nối đến cơ sở dữ liệu
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Bước 1: Tạo bảng tạm thời
    cursor.execute('''
        CREATE TABLE user_temp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            finances INTEGER,  -- Chỉnh sửa kiểu dữ liệu
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            key_api TEXT,
            is_admin INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    ''')

    # Bước 2: Sao chép dữ liệu
    cursor.execute('''
        INSERT INTO user_temp (id, email, password, first_name, last_name, phone, finances, created_at, key_api, is_admin, status)
        SELECT id, email, password, first_name, last_name, phone, CAST(finances AS INTEGER), created_at, key_api, is_admin, status
        FROM user
    ''')

    # Bước 3: Xóa bảng cũ
    cursor.execute('DROP TABLE user')

    # Bước 4: Đổi tên bảng tạm thời thành tên bảng cũ
    cursor.execute('ALTER TABLE user_temp RENAME TO user')

    # Lưu thay đổi và đóng kết nối
    conn.commit()
    conn.close()

# Gọi hàm để thực hiện
convert_finances_column()
