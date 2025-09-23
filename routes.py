from flask import Flask, render_template, request, flash, url_for, redirect, session
from app import app
from models import db, User, ParkingLot, ParkingSpot
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Context processor to make 'user' available in all templates
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(user=user)

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register', methods=["POST"])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    recheck_password = request.form.get('recheck_password')
    name = request.form.get('fullname')

    if not username or not password or not recheck_password:
        flash("Please fill all the fields.")
        return redirect(url_for('register'))

    if password != recheck_password:
        flash('Please recheck the password.')
        return redirect(url_for('register'))

    user = User.query.filter_by(username=username).first()
    if user:
        flash("Username already exists.")
        return redirect(url_for('register'))

    password_hash = generate_password_hash(password)

    new_user = User(username=username, passhash=password_hash, name=name)
    db.session.add(new_user)
    db.session.commit()
    flash("Registration successful! Please log in.")
    return redirect(url_for('login'))

@app.route('/login', methods=["POST"])
def login_page():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash("Please fill all fields.")
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash("Username doesn't exist.")
        return redirect(url_for('login'))

    if not check_password_hash(user.passhash, password):
        flash("Incorrect password.")
        return redirect(url_for('login'))

    session['user_id'] = user.id
    flash("Login successful.")
    if user.is_admin:
        return redirect(url_for('admin'))
    return redirect(url_for('user_dashboard'))

# creating a auth_required decorator for handling the login
def auth_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if 'user_id' in session:
            return func(*args, **kwargs)
        else:
            flash("Please log in first.")
            return redirect(url_for('login'))
    return inner

# admin decorator 

def admin_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if 'user_id'not in session:
            flash("please login first")
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            flash("you are not a admin")
            return redirect(url_for('user_dashboard'))
        return func(*args, **kwargs)
    return inner

@app.route('/user_dashboard')
@auth_required
def user_dashboard():
    # The 'user' variable is now automatically available
    # because of the context processor, so you don't need to pass it here.
    return render_template('user_dashboard.html')

@app.route('/profile')
@auth_required
def profile():
    return render_template('profile.html')

@app.route('/profile', methods=["POST"])
@auth_required
def update_profile():
    user = User.query.get(session['user_id'])
    
    username = request.form.get('username')
    cpassword = request.form.get('cpassword')
    npassword = request.form.get('npassword')
    name = request.form.get('name')

    if not cpassword or not name or not username:
        flash("Please enter the details.")
        return redirect(url_for('profile'))

    if not check_password_hash(user.passhash, cpassword):
        flash("Please fill the current password correctly.")
        return redirect(url_for('profile'))

    if username != user.username:
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists.")
            return redirect(url_for('profile'))
        user.username = username
        
    user.name = name
    
    if npassword:
        user.passhash = generate_password_hash(npassword)

    db.session.commit()
    flash("Successfully updated.")
    return redirect(url_for('profile'))

@app.route('/logout')
@auth_required
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/admin')
@admin_required
def admin():
    USER = User.query.get(session['user_id'])
    return render_template('admin.html',USER=USER)



@app.route('/create_lot' ,methods = ["POST"])
@admin_required
def create_lot():
    lot_name = request.form.get('location_name')
    pin_code = request.form.get('pin_code')
    city = request.form.get('adress')
    price = request.form.get('price')
    spots = request.form.get('spots')
    if not lot_name or not pin_code or not city or not price or not spots :
        flash("please fill all the details")
        return redirect(url_for('admin'))
    new_lot = ParkingLot(lot_name = lot_name , price = price , city = city,pin_code = pin_code , available_parking_spots =spots , is_active_lot = True)
    db.session.add(new_lot)
    db.session.flush()
    flash(f" '{lot_name}' created successfully")
    # now creating the parking spot inside the parkint lot this will reflect in the parking lot 
    new_spots = [ParkingSpot(lot_id = new_lot.id, spot_number ='P{:03d}'.format(i+1), occupied_status = False) for i in range(int(spots))]
    db.session.add_all(new_spots)
    db.session.commit()
    return redirect(url_for('admin'))



