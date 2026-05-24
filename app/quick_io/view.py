from flask import Blueprint, render_template

app_quick_io = Blueprint('app_quick_io', __name__)


@app_quick_io.route('/')
def index():
    """快速出入庫頁面"""
    from src import ADMIN_TITLE
    return render_template('quick_io/index.html', admin_title=ADMIN_TITLE)
