from flask import Blueprint, render_template, session, redirect, url_for, request, flash
import sqlite3
import os
import hmac
import secrets
import requests
import hmac
import hashlib
import logging
from decimal import Decimal
from wtforms import DecimalField, SubmitField
from flask_wtf import FlaskForm
from urllib.parse import urlencode
from wtforms import SubmitField
from flask_wtf.csrf import CSRFProtect
from wtforms.validators import DataRequired
from urllib.parse import urlencode  # Thêm dòng này để nhập khẩu urlencode
from .auth_controller import ResetPasswordForm  # Import form đổi mật khẩu từ auth_controller
COINPAYMENTS_API_URL = 'https://www.coinpayments.net/api.php'
COINPAYMENTS_PUBLIC_KEY = '9f8088c70dcfb6e69ee191b1e8c7c0c4332697605749e8cd284764ee24f06ccf'
COINPAYMENTS_PRIVATE_KEY = '11b420a140F1Bbc63C73DD6b75eD19DE54fbF3a162Cf2595ed980c02f888421c'

user_bp = Blueprint('user', __name__)
csrf = CSRFProtect()
logging.basicConfig(filename='app.log', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Hàm lấy thông tin người dùng từ database
def get_user_data(user_email):
    conn = sqlite3.connect('database.db')  # Thay đổi đường dẫn tới database của bạn
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE email = ?", (user_email,))
    columns = [column[0] for column in cursor.description]  # Lấy tên cột
    user_data = cursor.fetchone()

    # Chuyển đổi thành từ điển
    if user_data:
        user_dict = dict(zip(columns, user_data))
    else:
        user_dict = None

    conn.close()
    return user_dict

# Hàm cập nhật API key
def update_api_key(user_email):
    new_api_key = secrets.token_hex(32)  # Tạo API key mới
    conn = sqlite3.connect('database.db')  # Thay đổi đường dẫn tới database của bạn
    cursor = conn.cursor()
    cursor.execute("UPDATE user SET key_api = ? WHERE email = ?", (new_api_key, user_email))
    conn.commit()
    conn.close()
    return new_api_key

# Form cập nhật API key
class UpdateAPIKeyForm(FlaskForm):
    submit = SubmitField('Cập Nhật API Key')  # Nút submit đơn giản để cập nhật API key

@user_bp.route('/profile')
def profile():
    if 'user_email' in session:
        user_data = get_user_data(session['user_email'])
        api_key = user_data.get('key_api') if user_data else None  # Lấy api_key nếu có

        # Tạo form cập nhật API key
        update_api_key_form = UpdateAPIKeyForm()

        # Tạo form đổi mật khẩu (từ auth_controller)
        form = ResetPasswordForm()

        return render_template('frontend/profile.html', user=user_data, api_key=api_key, form=form, update_api_key_form=update_api_key_form)
    return redirect(url_for('auth.login'))

@user_bp.route('/profile/update_api_key', methods=['POST'])
def update_api_key_route():
    form = UpdateAPIKeyForm()  # Khởi tạo form
    if 'user_email' not in session:
        return redirect(url_for('auth.login'))

    if form.validate_on_submit():  # Xác nhận form đã được submit và CSRF token hợp lệ
        new_api_key = update_api_key(session['user_email'])  # Cập nhật API key
        return redirect(url_for('user.profile'))  # Chuyển hướng về trang profile

    return redirect(url_for('user.profile'))  # Nếu form không hợp lệ, quay về profile


def update_user_finances(user_email, amount):
    try:
        # Kết nối đến cơ sở dữ liệu
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Cập nhật số dư cho người dùng
        cursor.execute("UPDATE user SET finances = finances + ? WHERE email = ?", (amount, user_email))
        
        # Kiểm tra xem có dòng nào bị ảnh hưởng không
        if cursor.rowcount == 0:
            raise ValueError("Không tìm thấy người dùng với email: {}".format(user_email))
        
        # Lưu thay đổi vào cơ sở dữ liệu
        conn.commit()
    except sqlite3.Error as e:
        print(f"Có lỗi xảy ra: {e}")
    finally:
        # Đảm bảo đóng kết nối
        if conn:
            conn.close()
    
class AddFundsForm(FlaskForm):
    amount = DecimalField('Số tiền (USD)', validators=[DataRequired()])
    submit = SubmitField('Nạp tiền bằng BTC')

@user_bp.route('/add_funds', methods=['GET', 'POST'])
def add_funds():
    form = AddFundsForm()

    # Check if user is logged in
    if 'user_email' not in session:
        flash('Vui lòng đăng nhập để nạp tiền.', 'danger')
        return redirect(url_for('auth.login'))

    # Process the form if it's submitted
    if form.validate_on_submit():
        user_email = session['user_email']
        amount = form.amount.data  # Get the amount from the form
        
        # Prepare payload for CoinPayments API
        payload = {
            'cmd': 'create_transaction',
            'key': COINPAYMENTS_PUBLIC_KEY,
            'amount': amount,
            'currency1': 'USD',
            'currency2': 'BTC',
            'buyer_email': user_email,
            'ipn_url': url_for('user.coinpayments_webhook', _external=True),
            'item_name': 'Nạp tiền vào ví Bitcoin'
        }

        # Create HMAC hash
        # Note: Make sure all payload parameters are sorted before generating the HMAC
        payload_string = urlencode(sorted(payload.items()))
        payload['hash'] = hmac.new(
            COINPAYMENTS_PRIVATE_KEY.encode(),
            payload_string.encode(),
            hashlib.sha512
        ).hexdigest()

        try:
            # Send the request to CoinPayments API
            response = requests.post(COINPAYMENTS_API_URL, json=payload)
            result = response.json()

            if result['error'] == 'ok':
                invoice_url = result['result']['payment_url']
                return redirect(invoice_url)
            else:
                flash(f"Lỗi tạo hóa đơn: {result['error']}", "danger")
                return redirect(url_for('user.profile'))

        except Exception as e:
            flash(f"Có lỗi xảy ra: {str(e)}", "danger")
            return redirect(url_for('user.profile'))

    # Render the payment form if GET request or form not valid
    return render_template('frontend/payment.html', form=form)

@user_bp.route('/coinpayments/webhook', methods=['POST'])
def coinpayments_webhook():
    data = request.get_json()

    # Kiểm tra trạng thái giao dịch
    if data and data.get('status') == 'complete':
        user_email = data.get('buyer_email')
        amount_paid = data.get('amount')  # Số tiền đã thanh toán
        
        # Cộng số tiền vào ví của người dùng
        update_user_finances(user_email, amount_paid)

        return 'Thành công', 200

    return 'Thất bại', 400
