from flask import Blueprint, render_template
from datetime import datetime

app_docs = Blueprint('app_docs', __name__)


@app_docs.route('/')
def index():
    return render_template('docs/index.html', now=datetime.utcnow().year)
