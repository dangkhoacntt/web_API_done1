from flask import Flask, request
from flask_wtf.csrf import CSRFProtect
from controllers.auth_controller import auth_bp, google_bp
from controllers.user_controller import user_bp
from controllers.main_controller import main_bp
from controllers.admin_controller import admin_bp
from controllers.user_list_controller import user_list_bp
from db import get_db_connection, close_db_connection
from config import Config
from mail_config import mail
import logging
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from extensions import csrf

app = Flask(__name__, template_folder='views')
app.config.from_object(Config)

# Thiết lập secret key cho CSRF
app.config['SECRET_KEY'] = 'hm1234'
csrf.init_app(app)
# Khởi tạo CSRFProtect
csrf = CSRFProtect(app)


# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Đóng kết nối DB sau khi request kết thúc
@app.teardown_appcontext
def teardown_db(exception):
    close_db_connection(exception)

# Khởi tạo mail
mail.init_app(app)

# Đăng ký các blueprint, bao gồm Google OAuth
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_list_bp)
app.register_blueprint(google_bp, url_prefix="/google_login")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
