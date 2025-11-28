from flask import Flask , request,render_template


app = Flask(__name__)

from controllers import config
from models import models
from controllers import routes

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)
