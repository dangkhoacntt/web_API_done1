from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_mail import Message
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email
from db import get_db_connection
import hashlib
import logging
from flask_mail import Mail, Message
import random
from flask_wtf.csrf import CSRFProtect
import os
from werkzeug.security import generate_password_hash, check_password_hash
from models import create_user, get_user, update_user_password
from mail_config import mail
from flask_dance.contrib.google import make_google_blueprint, google
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo



auth_bp = Blueprint('auth', __name__)
logging.basicConfig(level=logging.DEBUG)



def generate_api_key():
    return hashlib.md5(os.urandom(16)).hexdigest()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    submit = SubmitField('Register')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    current_password = PasswordField('Mật Khẩu Hiện Tại', validators=[DataRequired()])
    new_password = PasswordField('Mật Khẩu Mới', validators=[DataRequired()])
    confirm_password = PasswordField('Nhập Lại Mật Khẩu', validators=[DataRequired(), EqualTo('new_password')])


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()  # Khởi tạo form đăng nhập
    if form.validate_on_submit():  # Kiểm tra dữ liệu form
        email = form.email.data
        password = form.password.data
        remember_me = request.form.get('remember_me')

        user = get_user(email, hash_password(password))  # Tìm người dùng theo email và mật khẩu đã hash
        if user:
            # Kiểm tra trạng thái tài khoản
            if user['status'] != 'active':
                flash('Tài khoản của bạn đã bị khóa hoặc không hoạt động. Vui lòng liên hệ với admin.', 'danger')
                return redirect(url_for('auth.login'))

            # Đăng nhập thành công, lưu thông tin vào session
            session['user_email'] = user['email']
            session['user_finances'] = user['finances']
            flash('Đăng nhập thành công!', 'success')

            response = redirect(url_for('main.home'))

            # Nếu người dùng chọn ghi nhớ tài khoản
            if remember_me:
                response.set_cookie('user_email', user['email'], max_age=30*24*60*60)  # Lưu trong 30 ngày
            else:
                response.set_cookie('user_email', '', expires=0)  # Xóa cookie nếu không ghi nhớ

            return response
        else:
            flash('Thông tin đăng nhập không chính xác. Vui lòng thử lại.', 'danger')

    # Lấy email từ cookie nếu có
    user_email = request.cookies.get('user_email', '')
    return render_template('frontend/login.html', form=form, user_email=user_email)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()  # Instantiate the registration form
    if form.validate_on_submit():  # Validate the form data
        email = form.email.data
        password = form.password.data
        first_name = form.first_name.data
        last_name = form.last_name.data

        if get_user(email):
            flash('Email đã được đăng ký.', 'danger')
        else:
            key_api = generate_api_key()
            create_user(email, hash_password(password), first_name, last_name, key_api)
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('frontend/register.html', form=form)

@auth_bp.route('/logout')
def logout():
    session.pop('user_email', None)
    session.clear()  # Xóa tất cả thông tin phiên
    flash('Bạn đã đăng xuất thành công.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password/', methods=['GET', 'POST'])
def change_password():
    if 'user_email' not in session:
        flash('Please log in to change your password.', 'danger')
        return redirect(url_for('auth.login'))

    email = session['user_email']
    user = get_user(email)

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_new_password = request.form['confirm_password']  # Confirm new password field

        # Hash the current password to verify
        hashed_current_password = hash_password(current_password)

        if user and user['password'] == hashed_current_password:
            if new_password == confirm_new_password:
                # Hash the new password and update in the database
                update_user_password(user['id'], hash_password(new_password))

                # Clear session after successful password change
                session.clear()

                flash('Your password has been updated! Please log in again.', 'success')
                return redirect(url_for('auth.login'))  # Redirect to login after session is cleared
            else:
                flash('New passwords do not match. Please try again.', 'danger')
        else:
            flash('Current password is incorrect.', 'danger')

    return render_template('frontend/profile.html', user=user)



class VerifyCodeForm(FlaskForm):
    code = StringField('Verification Code', validators=[DataRequired()])
    submit = SubmitField('Verify')

class SetNewPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Set Password')

def send_verification_email(email, verification_code):
    msg = Message('Mã xác thực',
                  sender='cubom882001@gmail.com',  # Thay bằng địa chỉ email của bạn
                  recipients=[email])
    msg.body = f'Mã xác thực của bạn là: {verification_code}'
    
    try:
        mail.send(msg)
        print(f'Email đã được gửi đến {email}')
    except Exception as e:
        print(f'Lỗi khi gửi email: {e}')
@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    form = ResetPasswordRequestForm()  # Initialize the form
    if form.validate_on_submit():  # Check if form data is valid
        email = form.email.data
        print(f"[DEBUG] Email submitted for password reset: {email}")

        # Check if the email exists in the database
        user = get_user(email)
        if user:
            print(f"[DEBUG] User found: {user}")
            # Generate verification code
            verification_code = random.randint(100000, 999999)
            print(f"[DEBUG] Generated verification code: {verification_code}")

            # Send the verification code via email
            send_verification_email(email, verification_code)

            # Store verification code and email in the session
            session['verification_code'] = verification_code
            session['user_email'] = email
            print(f"[DEBUG] Verification code and email stored in session")

            flash('A verification code has been sent to your email.', 'info')
            return redirect(url_for('auth.verify_code'))
        else:
            print(f"[DEBUG] No user found for email: {email}")
            flash('Email not found.', 'danger')

    return render_template('frontend/reset_password.html', form=form)

@auth_bp.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    form = VerifyCodeForm()
    print(f"[DEBUG] Verification code route accessed")

    if 'verification_code' not in session:
        print("[DEBUG] No verification code found in session")
        flash('No verification code found. Please request a new code.', 'danger')
        return redirect(url_for('auth.reset_password'))

    if form.validate_on_submit():
        entered_code = form.code.data
        print(f"[DEBUG] Code entered by user: {entered_code}")
        print(f"[DEBUG] Code stored in session: {session['verification_code']}")

        if entered_code and int(entered_code) == session['verification_code']:
            print(f"[DEBUG] Verification successful")
            return redirect(url_for('auth.set_new_password'))
        else:
            print(f"[DEBUG] Verification failed: entered code {entered_code}, session code {session['verification_code']}")
            flash('Invalid verification code. Please try again.', 'danger')

    return render_template('frontend/verify_code.html', form=form)


@auth_bp.route('/set_new_password', methods=['GET', 'POST'])
def set_new_password():
    form = SetNewPasswordForm()
    print(f"[DEBUG] Set new password route accessed")

    if form.validate_on_submit():
        new_password = form.new_password.data
        print(f"[DEBUG] New password submitted")

        # Hash the new password
        hashed_password = hash_password(new_password)
        print(f"[DEBUG] New password hashed: {hashed_password}")

        # Update the password in the database
        try:
            conn = get_db_connection()
            conn.execute('UPDATE user SET password = ? WHERE email = ?', (hashed_password, session['user_email']))
            conn.commit()
            print(f"[DEBUG] Password updated in database for email: {session['user_email']}")
            conn.close()

            flash('Your password has been updated!', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"[ERROR] Failed to update password: {e}")
            flash('An error occurred while updating the password. Please try again.', 'danger')

    return render_template('frontend/set_new_password.html', form=form)

@auth_bp.route('/clear_session', methods=['GET'])
def clear_session():
    session.pop('verification_code', None)
    session.pop('user_email', None)
    return redirect(url_for('auth.reset_password'))
    

