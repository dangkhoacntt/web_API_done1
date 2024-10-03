import sqlite3
from flask import g, current_app

def get_db_connection():
    if 'db_connection' not in g:
        g.db_connection = sqlite3.connect(current_app.config['DATABASE'])
        g.db_connection.row_factory = sqlite3.Row
    return g.db_connection

def close_db_connection(exception=None):
    db_connection = g.pop('db_connection', None)
    if db_connection is not None:
        db_connection.close()