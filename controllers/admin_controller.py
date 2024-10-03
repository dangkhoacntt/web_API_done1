import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from functools import wraps
from flask_wtf import FlaskForm
from db import get_db_connection
import hashlib
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email
import os
from models import create_user, get_user
from flask import jsonify
from extensions import csrf 
# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)  # Cấu hình để ghi log ở mức độ DEBUG
logger = logging.getLogger(__name__)  # Tạo logger

def generate_api_key():
    return hashlib.md5(os.urandom(16)).hexdigest()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

admin_bp = Blueprint('admin', __name__)

def is_admin_user(email):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM user WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    
    # Kiểm tra xem email có tồn tại và is_admin có phải là 1 không
    logger.debug(f"Checking if user {email} is admin.")
    return result is not None and result[0] == 1
@admin_bp.route('/chart')
def chart():
    # Lấy dữ liệu từ đâu đó (ví dụ từ database hoặc API)
    sales_data = [
        {"Product": "Wireless Headphones", "BuyerEmail": "john@test.com", "PurchaseDate": "2024-08-01", "Country": "USA", "Price": 99.0, "Refunded": "NO", "Currency": "USD", "Quantity": 2},
        # Các mục khác...
    ]
    
    return render_template('backend/chart.html', sales_data=sales_data)
@admin_bp.route('/admin')
def admin_dashboard():
    if 'admin_email' in session and is_admin_user(session['admin_email']):
        logger.info(f"Admin {session['admin_email']} accessed the dashboard.")
        return render_template('backend/home.html')
    
    logger.warning(f"Access denied for {session.get('admin_email', 'unknown')} to admin dashboard.")
    flash('Truy cập bị từ chối. Chỉ dành cho quản trị viên.', 'danger')
    return redirect(url_for('admin.login'))

class AdminLoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def login():
    form = AdminLoginForm()  # Khởi tạo form đăng nhập admin

    if form.validate_on_submit():  # Kiểm tra dữ liệu hợp lệ
        email = form.email.data
        password = form.password.data
        remember_me = form.remember_me.data

        user = get_user(email, hash_password(password))
        if user and is_admin_user(email):
            session['admin_email'] = user['email']
            flash('Đăng nhập admin thành công!', 'success')
            logger.info(f"Admin {email} logged in successfully.")

            response = redirect(url_for('admin.admin_dashboard'))

            if remember_me:
                response.set_cookie('admin_email', user['email'], max_age=30*24*60*60)
            else:
                response.set_cookie('admin_email', '', expires=0)

            return response
        else:
            logger.warning(f"Failed login attempt for {email}.")
            flash('Tài khoản không phải là admin hoặc thông tin đăng nhập không chính xác.', 'danger')

    return render_template('backend/login.html', form=form)

class BlockUserForm(FlaskForm):
    submit = SubmitField('Khóa tài khoản', validators=[DataRequired()])

@admin_bp.route('/admin/block_user/<int:user_id>', methods=['POST'])
def block_user(user_id):
    if not is_admin_user(session.get('admin_email', None)):
        return jsonify({'success': False, 'message': 'Bạn không có quyền thực hiện thao tác này.'}), 403

    conn = get_db_connection()
    conn.execute('UPDATE user SET status = ? WHERE id = ?', ('banned', user_id))
    conn.commit()
    conn.close()

    logger.info(f'User {user_id} has been blocked by admin {session["admin_email"]}.')
    return jsonify({'success': True, 'message': f'Tài khoản người dùng {user_id} đã bị khóa.'})



def get_user_from_key_api(key_api):
    if not key_api:
        return None  # Trả về None nếu không có key_api

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE key_api = ?", (key_api,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            'id': user[0],  # Giả sử cột 'id' là cột đầu tiên trong bảng `user`
            'email': user[1],  # Giả sử cột 'email' là cột thứ hai
            'finances': user[5],  # Giả sử cột 'finances' là cột thứ sáu
            'key_api': user[6],  # Giả sử cột 'key_api' là cột thứ bảy
        }
    return None  # Trả về None nếu không tìm thấy người dùng

# Trừ tiền trong tài khoản người dùng
def deduct_finances(email, amount):
    conn = get_db_connection()
    conn.execute('UPDATE user SET finances = finances - ? WHERE email = ?', (amount, email))
    conn.commit()
    conn.close()

# Hoàn tiền vào tài khoản người dùng
def refund_finances(email, amount):
    conn = get_db_connection()
    conn.execute('UPDATE user SET finances = finances + ? WHERE email = ?', (amount, email))
    conn.commit()
    conn.close()

# Ghi lại hoạt động API
def log_api_usage(user_id, key_api, link_api, action, success):
    conn = get_db_connection()
    conn.execute('INSERT INTO api_usage (user_id, key_api, link_api, action, success) VALUES (?, ?, ?, ?, ?)',
                 (user_id, key_api, link_api, action, success))
    conn.commit()
    conn.close()

# Route API để xử lý CAPTCHA hoặc các yêu cầu khác của người dùng
@admin_bp.route('/api/v1/resource', methods=['POST'])
@csrf.exempt # Tắt CSRF cho route này
def resource():
    api_key = request.headers.get('API-Key')
    
    # Kiểm tra và xử lý các thao tác liên quan đến api_key
    user = get_user_from_key_api(api_key)
    if not user:
        return jsonify({"message": "Invalid API Key"}), 401

    finances = int(user['finances'])
    if finances <= 0:
        return jsonify({"message": "Insufficient balance"}), 400

    # Giả sử đây là yêu cầu kiểm tra CAPTCHA
    captcha_success = request.json.get('success')
    amount = 1

    # Trừ tiền trong tài khoản
    deduct_finances(user['email'], amount)

    if captcha_success:
        log_api_usage(user['id'], api_key, request.path, request.method, True)
        return jsonify({"message": "CAPTCHA solved successfully", "finances": finances - amount}), 200
    else:
        # Hoàn tiền nếu CAPTCHA thất bại
        refund_finances(user['email'], amount)
        log_api_usage(user['id'], api_key, request.path, request.method, False)
        return jsonify({"message": "CAPTCHA failed, finances refunded", "finances": finances}), 200

@admin_bp.route('/api/user/<int:user_id>/usage', methods=['GET'])
def get_api_usage(user_id):
    conn = get_db_connection()
    usage_details = conn.execute(
        '''
        SELECT au.id, au.user_id, au.key_api, au.link_api, au.action, au.success, au.usage_timestamp, u.finances 
        FROM api_usage au
        JOIN user u ON au.user_id = u.id 
        WHERE au.user_id = ? 
        ORDER BY u.finances DESC, au.usage_timestamp DESC
        ''',
        (user_id,)
    ).fetchall()
    conn.close()
    usage_data = [
        {
            'id': row[0],
            'user_id': row[1],
            'key_api': row[2],
            'link_api': row[3],
            'action': row[4],
            'success': row[5],
            'usage_timestamp': row[6],
            'finances': row[7]  # Thêm trường finances
        } for row in usage_details
    ]

    return jsonify(usage_data)

@admin_bp.route('/api/search_users', methods=['GET'])
def search_users():
    query = request.args.get('query', '')  # Lấy truy vấn tìm kiếm từ tham số URL
    conn = get_db_connection()

    # Sử dụng truy vấn SQL để tìm kiếm người dùng theo email, key_api, hoặc finances
    users = conn.execute("""
        SELECT id, email, key_api, created_at, status, finances 
        FROM user 
        WHERE email LIKE ? OR key_api LIKE ? OR finances LIKE ?
    """, ('%' + query + '%', '%' + query + '%', '%' + query + '%')).fetchall()
    
    conn.close()

    # Chuyển đổi kết quả thành danh sách dictionary
    user_data = [
        {
            'id': row[0],
            'email': row[1],
            'key_api': row[2],
            'created_at': row[3],
            'status': row[4],
            'finances': row[5]  # Thêm finances vào dữ liệu trả về
        } for row in users
    ]

    return jsonify({'users': user_data})
