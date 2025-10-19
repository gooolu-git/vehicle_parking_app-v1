from flask import Flask, render_template, request, flash, url_for, redirect, session
from app import app
from models import db, User, ParkingLot, ParkingSpot ,Bookedspot
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps 
from sqlalchemy import func
from datetime import datetime
from math import ceil

## 1. IMPORTS AND CONTEXT PROCESSOR

# Context processor to make 'user' available in all templates
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(user=user)

# ----------------------------------------------------------------------
## 2. DECORATORS

# Authentication required decorator for standard users
def auth_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if 'user_id' in session:
            return func(*args, **kwargs)
        else:
            flash("Please log in first.")
            return redirect(url_for('login'))
    return inner

# Admin required decorator
def admin_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if 'user_id'not in session:
            flash("Please log in first.")
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            flash("You are not an admin.")
            return redirect(url_for('user_dashboard'))
        return func(*args, **kwargs)
    return inner

# ----------------------------------------------------------------------
## 3. PUBLIC AND AUTHENTICATION ROUTES

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
        flash('Passwords do not match.')
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
    
    deleted_spot = User.query.filter_by(username=username , is_active_user=True).first()
    if not deleted_spot:
        flash("You are Blocked .")
        return redirect(url_for('login'))

    if not check_password_hash(user.passhash, password):
        flash("Incorrect password.")
        return redirect(url_for('login'))

    session['user_id'] = user.id
    flash("Login successful.")
    if user.is_admin:
        return redirect(url_for('admin'))
    return redirect(url_for('user_dashboard'))

@app.route('/logout')
@auth_required
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.")
    return redirect(url_for('login'))

# ----------------------------------------------------------------------
## 4. SHARED UTILITY ROUTE

# Returns to the appropriate dashboard based on user role
@app.route('/return_to_dashboard')
@auth_required
def return_to_dashboard():
    user = User.query.get(session['user_id'])
    if user.is_admin:
        return redirect(url_for('admin'))
    return redirect(url_for('user_dashboard'))

# to update profile for admin and users 
@app.route('/profile')
@auth_required
def profile():
    user = User.query.get(session['user_id'])
    return render_template('profile.html', USER=user)

@app.route('/profile', methods=["POST"])
@auth_required
def update_profile():
    user = User.query.get(session['user_id'])
    
    username = request.form.get('username')
    cpassword = request.form.get('cpassword')
    npassword = request.form.get('npassword')
    name = request.form.get('name')

    if not cpassword or not name or not username:
        flash("Please enter the details and current password.")
        return redirect(url_for('profile'))

    if not check_password_hash(user.passhash, cpassword):
        flash("Please fill the current password correctly.")
        return redirect(url_for('profile'))

    if username != user.username:
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists.")
            return redirect(url_for('profile'))
        user.usernaedit_lotsme = username
        
    user.name = name
    
    if npassword:
        user.passhash = generate_password_hash(npassword)

    db.session.commit()
    flash("Successfully updated.")
    return redirect(url_for('return_to_dashboard'))


# ----------------------------------------------------------------------
## 5. USER ROUTES

@app.route('/user_dashboard')
@auth_required
def user_dashboard():
    user_id = session['user_id']
    all_lots = ParkingLot.query.all()
    lots = []
    
    # Compile lot details including spot availability
    for lot in all_lots:
        unoccupied_spots_count = ParkingSpot.query.filter_by(occupied_status=False, lot_id=lot.id).count()
        occupied_spots_count = ParkingSpot.query.filter_by(occupied_status=True, lot_id=lot.id).count()
        lots.append({
            'id': lot.id,
            'lot_name': lot.lot_name,
            'city': lot.city,
            'pin_code': lot.pin_code,
            'available_parking_spots': unoccupied_spots_count,
            'occupied_spots_count': occupied_spots_count,
            'price': lot.price,
            'lot_object': lot
        })

    # Check for active booking
    booked_spot_details = Bookedspot.query.filter_by(user_id=user_id, vehicle_released=False).first()
    if not booked_spot_details:
        message = "No Active Bookings Available click Book Spot"
        return render_template('user_dashboard.html', lots=lots, message=message)
    
    # Fetch details for the active booking
    booked_spot = ParkingSpot.query.get(booked_spot_details.spot_id)
    booked_lot = ParkingLot.query.get(booked_spot.lot_id)
    user_booked = User.query.get(user_id)

    return render_template('user_dashboard.html', lots=lots, booked_spot_details=booked_spot_details,
                           user_booked=user_booked, booked_lot=booked_lot, booked_spot=booked_spot)

@app.route('/spot_list')
@auth_required
def spot_list():
    all_lots = ParkingLot.query.all()
    lots = []
    for lot in all_lots:
        unoccupied_spots_count = ParkingSpot.query.filter_by(occupied_status=False, lot_id=lot.id).count()
        occupied_spots_count = ParkingSpot.query.filter_by(occupied_status=True, lot_id=lot.id).count()
        lots.append({
            'id': lot.id,
            'lot_name': lot.lot_name,
            'city': lot.city,
            'pin_code': lot.pin_code,
            'available_parking_spots': unoccupied_spots_count,
            'occupied_spots_count': occupied_spots_count,
            'price': lot.price,
            'lot_object': lot
        })
    return render_template('spot_list.html', lots=lots)

@app.route('/book_spot/<int:lot_id>')
@auth_required
def book_spot(lot_id):
    user = User.query.get(session['user_id'])
    # Check if the user already has an active booking
    if Bookedspot.query.filter_by(user_id=user.id, vehicle_released=False).first():
        flash("You already have an active booking.")
        return redirect(url_for('user_dashboard'))
    
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    if not spots:
        flash("Invalid lot or no spots available.")
        return redirect(url_for('user_dashboard'))

    return render_template('lots_list.html', spots=spots)    

@app.route('/book_this_spot/<int:spot_id>')
@auth_required
def book_this_spot(spot_id):
    user = User.query.get(session['user_id'])
    spot = ParkingSpot.query.get(spot_id)

    if spot is None:
        flash("Spot not available.")
        return redirect(url_for('spot_list'))
        
    if spot.occupied_status:
        flash("Spot is occupied.")
        return redirect(url_for('book_spot', lot_id=spot.lot_id))

    # Check for active booking
    if Bookedspot.query.filter_by(user_id=user.id, vehicle_released=False).first():
        flash("You already have an active booking.")
        return redirect(url_for('user_dashboard'))
    
    
    lot = ParkingLot.query.get(spot.lot_id)
    available = ParkingSpot.query.filter_by(occupied_status=False, lot_id=spot.lot_id).count()
    return render_template('book_this_spot.html', spot=spot, lot=lot, available=available)

@app.route('/book_this_spot/<int:spot_id>', methods=["POST"])
@auth_required
def booked_spot(spot_id):
    spot = ParkingSpot.query.get(spot_id)

    if not spot:
        flash("Spot not available.")
        return redirect(url_for('user_dashboard'))
    is_deleted = spot.deleted_spot
    if not is_deleted:
        flash("cant book a deactive spot")
        return redirect(url_for('book_spot', lot_id=spot.lot_id))
    user = User.query.get(session['user_id'])
    
    # Check again for active booking before committing
    if Bookedspot.query.filter_by(user_id=user.id, vehicle_released=False).first():
        flash("You already have an active booking.")
        return redirect(url_for('user_dashboard'))
    
    parked_spot = ParkingSpot.query.filter_by(id=spot_id).first()

    
    vehicle_number = request.form.get("vehicle_number")
    user_id = session['user_id']
    
    # Mark spot as occupied
    spot.occupied_status = True
    
    # Create new booking record
    booked = Bookedspot(user_id=user_id, spot_id=spot_id, vehicle_number=vehicle_number)
    db.session.add(booked)
    db.session.commit()
    flash("Booking successful! Your entry time has been recorded.")
    return redirect(url_for('user_dashboard'))

@app.route('/release_spot/<int:book_id>/<int:spot_id>')
@auth_required
def release_spot(book_id, spot_id):
    booking = Bookedspot.query.get(book_id)
    parking_spot = ParkingSpot.query.get(spot_id)
    
    if not booking or booking.vehicle_released:
        flash("Invalid or already released spot.")
        return redirect(url_for('user_dashboard'))
        
    parking_lot = ParkingLot.query.get(parking_spot.lot_id)
    parking_cost_per_hour = parking_lot.price
    
    # 1. Update Booking and Parking Spot Status
    booking.vehicle_released = True
    booking.exit_timing = datetime.now()
    parking_spot.occupied_status = False
    
    # 2. Calculate Cost
    entry = booking.entry_timing
    exit_time = booking.exit_timing
    
    time_difference = exit_time - entry
    total_seconds = time_difference.total_seconds()
    total_hours = total_seconds / 3600
    
    # Cost calculation: Round up to the nearest whole hour using ceil()
    billed_hours = ceil(total_hours)
    cost = billed_hours * parking_cost_per_hour
    
    # 3. Save Cost and Commit
    booking.parking_cost = cost
    db.session.commit()
    
    flash(f"Vehicle released! Total cost: INR{cost}.")
    return redirect(url_for('user_dashboard'))

@app.route('/booking_history')
@auth_required
def booking_history():
    user = User.query.get(session['user_id'])
    
    # Get all released bookings for the user
    released_bookings = Bookedspot.query.filter_by(user_id=user.id, vehicle_released=True).all()
    
    occupied_history = []
    for booking in released_bookings:
        spot = ParkingSpot.query.get(booking.spot_id)
        lot = ParkingLot.query.get(spot.lot_id)
        
        occupied_history.append({
            'bookedspot_id': booking.id,
            'location_name': lot.lot_name,
            'address': lot.city,
            'vehicle': booking.vehicle_number,
            'entry': booking.entry_timing,
            'exit': booking.exit_timing,
            'cost': booking.parking_cost
        })
    return render_template('booking_history.html', occupied_history=occupied_history)

# ----------------------------------------------------------------------
## 6. ADMIN ROUTES

@app.route('/admin')
@admin_required
def admin():
    user = User.query.get(session['user_id'])
    all_lots = ParkingLot.query.all()
    lots = []
    
    for lot in all_lots:
        unoccupied_spots_count = ParkingSpot.query.filter_by(occupied_status=False, lot_id=lot.id).count()
        occupied_spots_count = ParkingSpot.query.filter_by(occupied_status=True, lot_id=lot.id).count()
        lots.append({
            'id': lot.id,
            'lot_name': lot.lot_name,
            'city': lot.city,
            'pin_code': lot.pin_code,
            'available_parking_spots': unoccupied_spots_count,
            'occupied_spots_count': occupied_spots_count,
            'lot_object': lot
        })
    user_count = User.query.filter_by(is_active_user = True, is_admin=False).count()   
    bookings_count = ParkingSpot.query.filter_by(occupied_status=True).count()
    lot_count = ParkingLot.query.count()
    total_revenue = db.session.query(func.sum(Bookedspot.parking_cost)).scalar()
    
    # Ensure variables are initialized if query returns None
    total_revenue = total_revenue if total_revenue is not None else 0
    
    return render_template('admin.html',  lots=lots, total_revenue=total_revenue, 
                           lot_count=lot_count, bookings_count=bookings_count, user_count=user_count) 

@app.route('/lot_list')
@admin_required
def lot_list():
    all_lots = ParkingLot.query.all()
    lots = []
    for lot in all_lots:
        unoccupied_spots_count = ParkingSpot.query.filter_by(occupied_status=False, lot_id=lot.id).count()
        occupied_spots_count = ParkingSpot.query.filter_by(occupied_status=True, lot_id=lot.id).count()
        lots.append({
            'id': lot.id,
            'lot_name': lot.lot_name,
            'city': lot.city,
            'pin_code': lot.pin_code,
            'available_parking_spots': unoccupied_spots_count,
            'occupied_spots_count': occupied_spots_count,
            'lot_object': lot
        })
    return render_template('admin_add_lot.html', lots=lots)

@app.route('/create_lot', methods=["POST"])
@admin_required
def create_lot():
    lot_name = request.form.get('location_name')
    pin_code = request.form.get('pin_code')
    city = request.form.get('adress')
    price = request.form.get('price')
    spots_count = request.form.get('spots')
    
    if not all([lot_name, pin_code, city, price, spots_count]):
        flash("Please fill all the details.")
        return redirect(url_for('admin'))
        
    try:
        spots_count = int(spots_count)
        price = float(price)
    except ValueError:
        flash("Price and Spot count must be numbers.")
        return redirect(url_for('admin'))

    new_lot = ParkingLot(lot_name=lot_name, price=price, city=city, pin_code=pin_code, 
                         available_parking_spots=spots_count, deleted_lot=True)
    db.session.add(new_lot)
    db.session.flush() # Get the new_lot.id before committing

    # Create parking spots for the new lot
    def create_spot(lot_id,spots_count):
        new_spots = [ParkingSpot(lot_id=lot_id, spot_number='P{:03d}'.format(i+1), occupied_status=False) 
                 for i in range(spots_count)]      
        db.session.add_all(new_spots)
    
    lot_id = new_lot.id
    create_spot(lot_id,spots_count)
    db.session.commit()
    flash(f"Parking Lot '{lot_name}' created successfully with {spots_count} spots.")
    return redirect(url_for('lot_list'))

@app.route('/see_spots/<int:sid>')
@admin_required
def see_lots(sid):
    lots=ParkingLot.query.filter_by(id=sid).first()
    spots = ParkingSpot.query.filter_by(lot_id=sid).all()
    unoccupied_spots_count = ParkingSpot.query.filter_by(occupied_status=False, lot_id=lots.id).count()
    occupied_spots_count = ParkingSpot.query.filter_by(occupied_status=True, lot_id=lots.id).count()
    
    return render_template('admin_spot_view.html', lots=lots, spots=spots ,unoccupied_spots_count=unoccupied_spots_count,occupied_spots_count=occupied_spots_count)
@app.route('/view_this_spot_details/<int:sid>')
@admin_required
def view_this_spot_details(sid):
    parked_spot = ParkingSpot.query.filter_by(id=sid,occupied_status=True).first()
    if not parked_spot:
        flash("Not a Booked Spot")
    spot = Bookedspot.query.filter_by(spot_id=sid).first()
    lot_id = parked_spot.lot_id
    lot = ParkingLot.query.filter_by(id=lot_id).first()
    user_id = spot.user_id
    user = User.query.filter_by(id=user_id).first()
    return render_template('admin_spot_user_details.html', spot=spot , parked_spot=parked_spot,lot=lot,user=user)

@app.route('/deactivate_this_spot/<int:sid>')
@admin_required
def deactivate_this_spot(sid):
    parked_spot = ParkingSpot.query.filter_by(id=sid).first()
    if not parked_spot:
        flash("Parking spot not found.")
        return redirect(url_for('lot_list'))
    
    lot = ParkingLot.query.filter_by(id=parked_spot.lot_id).first()
    return render_template('admin_deactivate_spot.html', parked_spot=parked_spot, lot=lot)

@app.route('/deactivate_this_spot/<int:sid>',methods=["POST"])
@admin_required
def deactivated_spot(sid):
    parked_spot = ParkingSpot.query.filter_by(id=sid).first()

    if not parked_spot:
        flash("Spot not found.") 
        return redirect(url_for('lot_list'))

    # see is the spot is occupied then we not delete
    if parked_spot.occupied_status and not parked_spot.deleted_spot:
        flash("Cannot deactivate an occupied spot")
        return redirect(url_for('see_lots', sid=parked_spot.lot_id))
    
    # see between deleted and undelted
    parked_spot.deleted_spot = not parked_spot.deleted_spot
    db.session.commit() 

    if parked_spot.deleted_spot:
        flash(f"Spot {parked_spot.spot_number} successfully activated.")
    else:
        flash(f"Spot {parked_spot.spot_number} successfully dectivated.")
    return redirect(url_for('see_lots', sid=parked_spot.lot_id))
    



@app.route('/edit_lots/<int:sid>')
@admin_required
def edit_lots(sid):
    lots=ParkingLot.query.filter_by(id=sid).first()
    spots_count = ParkingSpot.query.filter_by(lot_id=sid).count()    
    return render_template('admin_edit_lot.html',lots=lots,spots_count=spots_count)



# @app.route('/edit_lots/<int:sid>',methods=["POST"])
# @admin_required
# def edite_lot(sid):
#     lot = ParkingLot.query.filter_by(id=sid).first()
#     spots_occupied = ParkingSpot.query.filter_by(lot_id=sid,occupied_status=True)
#     old_spot_count  = ParkingSpot.query.count()
#     new_spot_count = int(request.form.get('spots'))

#     lot.lot_name = request.form.get('location_name')
#     lot.pin_code = request.form.get('pin_code')
#     lot.city = request.form.get('adress') 
#     lot.price = float(request.form.get('price'))
    
#     #check if there is booked spot already then deny editing
#     if spots_occupied:
#         flash("Active boking found cant edit Spots")
#         return redirect(url_for('lot_list'))
#     lot.available_parking_spots =0
#     db.session.flush()

#     def create_spot(lot_id,spots_count):
#         new_spots = [ParkingSpot(lot_id=lot_id, spot_number='P{:03d}'.format(i+1), occupied_status=False) 
#                 for i in range(spots_count)]      
#         db.session.add_all(new_spots)
#     lot_id = lot.id
#     create_spot(lot_id,new_spot_count)
#     db.session.commit()
#     flash(f"spots updated for {lot.lot_name}")
#     return redirect(url_for('lot_list'))

    
        

@app.route('/edit_lots/<int:sid>', methods=["POST"])
@admin_required
def edited_lot(sid):
    # 1. Fetch lot details and current spot counts
    lot = ParkingLot.query.filter_by(id=sid).first_or_404() 
    old_spots_count = lot.available_parking_spots 
    
    # Counting currently occupied and active spots
    occupied_spots_count = ParkingSpot.query.filter_by(
        lot_id=sid, 
        occupied_status=True, 
        deleted_spot=True
    ).count()
    
    # Get new spot count from form
    new_spots_count = int(request.form.get('spots'))

    # 2. Check: New spots must be >= occupied spots
    if occupied_spots_count > new_spots_count:
        db.session.rollback()
        flash(f"Error: New spots ({new_spots_count}) less than occupied spots ({occupied_spots_count}).")
        return redirect(url_for('edit_lots', sid=lot.id))

    # 3. Update main lot details in session
    lot.lot_name = request.form.get('location_name')
    lot.pin_code = request.form.get('pin_code')
    lot.city = request.form.get('adress') 
    lot.price = float(request.form.get('price'))
    lot.available_parking_spots = new_spots_count
    
    # Flush: Lot table data updated temporarily
    db.session.flush() 

    # 4. Calculate spot difference
    spot_diff = new_spots_count - old_spots_count

    # 5. Case 1: Increase spots (spot_diff > 0)
    if spot_diff > 0:
        # First, reactivate soft-deleted spots
        reactivated_spots = ParkingSpot.query.filter_by(lot_id=sid, deleted_spot=False).limit(spot_diff).all()
        for spot in reactivated_spots:
            spot.deleted_spot = True
        
        spot_diff -= len(reactivated_spots)

        # If needed, create new spots with unique numbering
        if spot_diff > 0:
            # CORRECTED LOGIC: Find the highest existing spot number
            # We query the max of the spot_number column, cast to integer
            # We use db.session.query(func.max(CAST(ParkingSpot.spot_number AS INTEGER)))
            # Simple assumption: spot_number column contains only integer strings (e.g., '1', '2', '15')
            max_spot_number_str = db.session.query(func.max(ParkingSpot.spot_number)).filter_by(lot_id=sid).scalar()
            
            # Convert max number to int, default to 0 if no spots exist
            try:
                current_max = int(max_spot_number_str) if max_spot_number_str else 0
            except ValueError:
                # Fallback if spot_number is non-numeric (e.g., 'A1'). 
                # If this happens, you need to implement custom parsing logic.
                # For this example, we'll revert to counting, but this might cause future bugs if numbers are skipped.
                current_max = ParkingSpot.query.filter_by(lot_id=sid).count()
                
            new_spots = []
            for i in range(spot_diff):
                # Calculate the new spot number
                new_spot_number_int = current_max + i + 1
                new_spot_number = str(new_spot_number_int)
                #----------look_here---
                new_spots.append(ParkingSpot(
                    lot_id=sid,
                    spot_number=new_spot_number,
                    occupied_status=False,
                    deleted_spot=True
                ))
            db.session.add_all(new_spots)

    # 6. Case 2: Decrease spots (spot_diff < 0)
    elif spot_diff < 0:
        # Soft-delete unoccupied spots (set deleted_spot=False)
        spots_to_remove = ParkingSpot.query.filter_by(
            lot_id=sid, 
            occupied_status=False, 
            deleted_spot=True         
        ).order_by(
            ParkingSpot.spot_number.desc()
        ).limit(abs(spot_diff)).all()
        
        # Mark spots as inactive (soft-delete)
        for spot in spots_to_remove:
            spot.deleted_spot = False

    # 7. Final commit and redirect
    db.session.commit()
    
    flash(f"Parking lot '{lot.lot_name}' updated successfully.")
    return redirect(url_for('lot_list'))

@app.route('/delete_spots/<int:sid>')
@admin_required
def delete_lots(sid):
    lot = ParkingLot.query.filter_by(id=sid).first()
    active_bookings = ParkingSpot.query.filter_by(lot_id = sid ,occupied_status=True).count()
    if not lot:
        return redirect(url_for('lot_list'))
    if active_bookings:
        flash(f"{lot.lot_name} has active bookings cant delete it")
        return redirect(url_for('lot_list'))
    db.session.delete(lot)
    db.session.flush()
    db.session.commit()
    flash(f"{lot.lot_name } was successfully deleted !")
    return redirect(url_for('lot_list'))
    

@app.route('/user_list')
@admin_required
def user_list():
    all_users = User.query.all()
    user_count = User.query.filter_by(is_active_user = True, is_admin=False).count()
    bookings_count = ParkingSpot.query.filter_by(occupied_status=True).count()
    usermodel = []
    
    for user in all_users:
        if user.is_admin:
            continue
            
        current_spot_id = "NA"
        current_spot_number = "NA"
        
        # Check for active, unreleased bookings
        active_booking = Bookedspot.query.filter_by(user_id=user.id, vehicle_released=False).first()
        
        if active_booking:
            parking_spot = ParkingSpot.query.get(active_booking.spot_id)
            current_spot_id = parking_spot.id
            current_spot_number = parking_spot.spot_number

        usermodel.append({
            'id': user.id,
            'username': user.username,
            'name': user.name,
            'spot_id': current_spot_id,
            'spot_number': current_spot_number,
            'deleted_spot': user.is_active_user
        })
    return render_template('user_list.html', usermodel=usermodel, user_count=user_count, bookings_count=bookings_count)

@app.route('/deactivate_user/<int:uid>')
@admin_required
def deactivate_user(uid):
    user = User.query.get(uid)
    user_bid = user.id
    user_booked_spot = Bookedspot.query.filter_by(user_id=user_bid,vehicle_released=False).first()
    if not user or user.is_admin:
        flash("Invalid user or cannot deactivate admin.")
        return redirect(url_for('user_list'))
    if user_booked_spot:
        flash("sorry! user have active bookings ")
        return redirect(url_for('user_list'))   
    if user.is_active_user:
        user.is_active_user = False
        flash(f"User '{user.username}' successfully deactivated.")
        db.session.flush()
    else:
        user.is_active_user = True
        flash(f"User '{user.username}' successfully activated.")
        db.session.flush()
        
    db.session.commit()
    return redirect(url_for('user_list'))

#------------------------------------------user_summary---------------------------------------------------------
@app.route('/user_bookings_summary')
@auth_required
def user_bookings_summary():
    user = User.query.get(session['user_id'])
    user_id = user.id
    if not user:
        return render_template('error.html', message=f"User with ID {user_id} not found.")

    # CRUCIAL: Filtering by Bookedspot.user_id == user_id ensures only the logged-in user's data is aggregated.
    monthly_data = db.session.query(
        func.strftime('%Y-%m', Bookedspot.entry_timing).label('year_month'),
        func.count(Bookedspot.id).label('booking_count'),
        func.sum(Bookedspot.parking_cost).label('total_expenditure')
    ).filter(Bookedspot.user_id == user_id).group_by('year_month').order_by('year_month').all()

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    chart_labels = []
    booking_counts = []
    expenditure_data = []
    
    for row in monthly_data:
        year_month_str = row.year_month
        
        month_index = int(year_month_str.split('-')[1]) - 1 
        year_str = year_month_str.split('-')[0]
        
        label = f"{month_names[month_index]} {year_str}"
        
        chart_labels.append(label)
        booking_counts.append(row.booking_count)
        # Use 0.0 if parking_cost is None for a month (e.g., if no spots were released yet)
        expenditure_data.append(row.total_expenditure or 0.0)

    chart_json_data = {
        'labels': chart_labels,
        'booking_counts': booking_counts,
        'expenditure_data': expenditure_data,
        'username': user.name
    }

    return render_template('user_summary.html', chart_data=chart_json_data)




#------------------------------------admin_summary----------------------------------
@app.route('/admin_summary')
@admin_required
def admin_summary():
    # Total spots that are NOT deleted
    total_spots = db.session.query(func.count(ParkingSpot.id))
    # total_revenue = db.session.query(func.sum(ParkingSpot.occupied_status=False)).scalar()
    occupied_spots = ParkingSpot.query.filter_by(occupied_status=True,deleted_spot = True).count()
    unoccupied_spots = ParkingSpot.query.filter_by(occupied_status=False,deleted_spot = True).count()
    # Occupied spots: those with occupied_status = True and not deleted
    

    pie_chart_data = {
        'labels': ['Occupied', 'Unoccupied'],
        'data': [occupied_spots, unoccupied_spots]
    }

    # Monthly revenue from Bookedspot (only those with parking_cost not none)
    monthly_revenue = db.session.query(
        func.strftime('%Y-%m', Bookedspot.entry_timing).label('year_month'),
        func.sum(Bookedspot.parking_cost).label('total_revenue')
    ).filter(
        Bookedspot.parking_cost != None
    ).group_by('year_month').order_by('year_month').all()

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    bar_labels = []
    revenue_data = []

    for row in monthly_revenue:
        year_month_str = row.year_month
        month_index = int(year_month_str.split('-')[1]) - 1
        year_str = year_month_str.split('-')[0]
        label = f"{month_names[month_index]} {year_str}"
        bar_labels.append(label)
        revenue_data.append(row.total_revenue or 0.0)

    bar_chart_data = {
        'labels': bar_labels,
        'revenue': revenue_data
    }

    return render_template(
        'admin_summary.html',
        pie_chart_data=pie_chart_data,
        bar_chart_data=bar_chart_data
    )
