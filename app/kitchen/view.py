from flask import Blueprint, render_template

app_kitchen = Blueprint('app_kitchen', __name__)


@app_kitchen.route('/')
def index():
    return render_template('kitchen/index.html')
