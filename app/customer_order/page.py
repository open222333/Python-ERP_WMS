from flask import Blueprint, render_template

app_order_page = Blueprint('app_order_page', __name__)


@app_order_page.route('/')
def index():
    return render_template('order/index.html')
