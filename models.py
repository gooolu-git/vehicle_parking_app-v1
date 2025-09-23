from app import app 
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer , primary_key = True)
    username = db.Column(db.String(32) , unique = True, nullable=False)
    passhash = db.Column(db.String(256), nullable = False)
    name = db.Column(db.String(64), nullable=False)
    is_admin = db.Column(db.Boolean, nullable = False , default = False)
    # is_active_user = db.Column(db.Boolean, nullable = False , default = False)

    # spots where the users have acquired or booked the spot 
    acquired_spot = db.relationship("Bookedspot", backref="user", lazy=True)


# creating the parking place wehre many spots will be available
class ParkingLot(db.Model):
    id = db.Column(db.Integer , primary_key = True)
    lot_name = db.Column(db.String(256), nullable = False )
    price = db.Column(db.Float, nullable = False)
    city = db.Column(db.String(64), nullable = False)
    pin_code = db.Column(db.String(32), nullable = False)
    available_parking_spots = db.Column(db.Integer, nullable = False)
    is_active_lot = db.Column(db.Boolean, nullable = False, default = False)

    # each parking lot will have many parking spots
    parking_spot = db.relationship("ParkingSpot", backref="parking_lot", lazy=True, cascade="all,delete")


class ParkingSpot(db.Model):
    id = db.Column(db.Integer , primary_key = True)
    # we have to specify which parking lot this parking spot belongs to 
    lot_id = db.Column(db.Integer, db.ForeignKey(ParkingLot.id), nullable = False)
    occupied_status = db.Column(db.Boolean , nullable = False , default = False)
    spot_number = db.Column(db.String(6), nullable = False)
    # each parking spot can be booked many times
    booked_spots = db.relationship("Bookedspot", backref="parking_spot", lazy=True)


# spots where the users have acquired or booked the spot 
class Bookedspot(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    #many to many relation between the user and the parkingspot table
    spot_id = db.Column(db.Integer , db.ForeignKey(ParkingSpot.id) , nullable = False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable = False)

    entry_timing = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    exit_timing = db.Column(db.DateTime, nullable=True)

    parking_cost = db.Column(db.Float, nullable=True)
    vehicle_number = db.Column(db.String(64), nullable = False)
    vehicle_released = db.Column(db.Boolean, nullable = False , default = False)
with app.app_context():
    db.create_all()
    #checking if it is not admin 
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        password = generate_password_hash('admin')
        admin = User(username = 'admin',passhash = password , name = 'Admin', is_admin = True)
        db.session.add(admin)
        db.session.commit()