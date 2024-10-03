import hashlib
import logging
from db import get_db_connection

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email, password=None, first_name=None, last_name=None, key_api=None, is_admin=0):
    conn = get_db_connection()
    
    # Nếu không có mật khẩu được cung cấp, đặt giá trị mặc định
    if password is None:
        password = 'default_password'  # Hoặc giá trị khác mà bạn lựa chọn

    # Chèn người dùng vào bảng
    conn.execute('INSERT INTO user (email, password, first_name, last_name, key_api, is_admin) VALUES (?, ?, ?, ?, ?, ?)',
                 (email, password, first_name, last_name, key_api, is_admin))
    
    conn.commit()
    conn.close()


def get_user(email, password=None):
    conn = get_db_connection()
    if password:
        user = conn.execute('SELECT * FROM user WHERE email = ? AND password = ?', (email, password)).fetchone()
    else:
        user = conn.execute('SELECT * FROM user WHERE email = ?', (email,)).fetchone()
    return user

def update_user_password(user_id, hashed_password):
    conn = get_db_connection()
    conn.execute('UPDATE user SET password = ? WHERE id = ?', (hashed_password, user_id))
    conn.commit()
    conn.close()
