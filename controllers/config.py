from dotenv import load_dotenv
import os
from app import app


load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['TRACK_MODIFICATOIN'] = os.getenv('TRACK_MODIFICATION')
app.config['SECRET_KEY']  = os.getenv('SECRET_KEY')

