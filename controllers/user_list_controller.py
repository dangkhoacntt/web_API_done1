from flask import Blueprint, render_template, session, redirect, url_for, flash
from db import get_db_connection

user_list_bp = Blueprint('user_list', __name__)

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, key_api, created_at, status, finances FROM user")  # Thêm finances vào truy vấn
    users = [
        {'id': row[0], 'email': row[1], 'key_api': row[2], 'created_at': row[3], 'status': row[4], 'finances': row[5]}  # Thêm finances vào từ điển
        for row in cursor.fetchall()
    ]
    conn.close()
    return users

@user_list_bp.route('/admin/users')
def user_list():
    if 'admin_email' in session:
        users = get_all_users()
        return render_template('backend/user_list.html', users=users)
    
    flash('Truy cập bị từ chối. Chỉ dành cho quản trị viên.', 'danger')
    return redirect(url_for('admin.login'))
