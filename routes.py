from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, make_response, \
    send_file, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, mail, csrf  # initialized extensions
from models import *
from datetime import datetime
import logging
import json
import os
from werkzeug.utils import secure_filename

main_bp = Blueprint('main', __name__)

# =========================
# Home and Product Routes
# =========================

@main_bp.route('/admin/invoice-logos')
@login_required
def admin_invoice_logos():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    settings = StoreSettings.query.first()
    return render_template('admin/invoice_settings.html', settings=settings)


@main_bp.route('/admin/update-invoice-logos', methods=['POST'])
@login_required
def admin_update_invoice_logos():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)

    settings.invoice_logo_url = request.form.get('invoice_logo_url')
    settings.invoice_logo_position = request.form.get('invoice_logo_position')
    settings.invoice_logo_size = int(request.form.get('invoice_logo_size') or 0)
    settings.invoice_upi_logo_url = request.form.get('invoice_upi_logo_url')
    settings.invoice_upi_logo_position = request.form.get('invoice_upi_logo_position')
    settings.invoice_upi_logo_size = int(request.form.get('invoice_upi_logo_size') or 0)
    db.session.commit()
    flash('Invoice logo settings updated successfully', 'success')
    return redirect(url_for('main.admin_invoice_logos'))


@main_bp.route('/')
def index():
    user_agent = request.headers.get('User-Agent', '').lower()
    _ = any(x in user_agent for x in ['mobile', 'android', 'iphone', 'ipad'])  # reserved

    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
    settings = StoreSettings.query.first()

    featured_products = Product.query.filter_by(is_active=True, is_featured=True).limit(12).all()
    all_products = Product.query.filter_by(is_active=True).limit(20).all()
    return render_template(
        'zepto_index.html',
        categories=categories,
        featured_products=featured_products,
        all_products=all_products,
        settings=settings,
        store_settings=settings
    )


@main_bp.route('/products')
@main_bp.route('/products/<int:category_id>')
def products(category_id=None):
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = Product.query.filter_by(is_active=True)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if search:
        query = query.filter(Product.name.contains(search) | Product.name_tamil.contains(search))

    products = query.paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()
    selected_category = Category.query.get(category_id) if category_id else None

    categories_with_images = []
    for category in categories:
        sample_product = (
            Product.query.filter_by(category_id=category.id, is_active=True)
            .filter(Product.image_url.isnot(None)).first()
        )

        categories_with_images.append({
            'id': category.id,
            'name': category.name,
            'name_tamil': category.name_tamil,
            'image_url': sample_product.image_url if sample_product else '/static/images/placeholder.jpg'
        })

    return render_template(
        'products.html',
        products=products,
        categories=categories_with_images,
        selected_category=selected_category,
        search=search
    )


@main_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    weight_options = json.loads(product.weight_options) if product.weight_options else [0.5, 1, 2]
    return render_template('product_detail.html', product=product, weight_options=weight_options)

# =========================
# Authentication Routes
# =========================

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        current_app.logger.debug(f"Login attempt: email={email}")

        user = User.query.filter_by(email=email).first()

        if user:
            current_app.logger.debug(f"User found: {user.username}, active: {user.is_active}")
            current_app.logger.debug(f"Password check: {user.check_password(password)}")

            if user.is_active and user.check_password(password):
                login_user(user)
                next_page = request.args.get('next')

                if user.role in ('admin', 'storekeeper'):
                    flash(f'Welcome back, {user.username}!', 'success')
                    return redirect(url_for('main.admin_dashboard'))
                else:
                    flash(f'Welcome back, {user.username}!', 'success')
                    return redirect(next_page) if next_page else redirect(url_for('main.index'))
            else:
                flash('Invalid email or password', 'error')
        else:
            current_app.logger.debug("User not found")
            flash('Invalid email or password', 'error')

    return render_template('login.html')


@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return render_template('register.html')

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='customer'
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Registration successful!', 'success')
        return redirect(url_for('main.index'))

    return render_template('register.html')


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))

# =========================
# Cart Routes
# =========================

@csrf.exempt
@main_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    # Handle both JSON (AJAX) and form requests
    if request.is_json:
        data = request.get_json() or {}
        product_id = data.get('product_id')
        quantity = data.get('quantity', 0.0)
        try:
            product_id = int(product_id) if product_id is not None else None
            quantity = float(quantity) if quantity is not None else 0.0
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Invalid data'}), 400
    else:
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=float)

    if product_id is None or quantity is None:
        msg = 'Product and quantity are required'
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        return redirect(url_for('main.index'))

    if quantity <= 0:
        message = 'Quantity must be greater than zero'
        if request.is_json:
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'error')
        return redirect(url_for('main.product_detail', product_id=product_id))

    product = Product.query.get_or_404(product_id)

    # Resolve field aliases safely
    stock = getattr(product, 'stock_kg', None)
    if stock is None:
        stock = getattr(product, 'stock_quantity', None)

    min_qty_cfg = (
        getattr(product, 'min_quantity_kg', None)
        or getattr(product, 'min_qty', None)
        or getattr(product, 'min_order_quantity', None)
    )
    max_qty_cfg = (
        getattr(product, 'max_quantity_kg', None)
        or getattr(product, 'max_qty', None)
        or getattr(product, 'max_order_quantity', None)
    )

    # Validate quantity against stock and limits
    if stock is not None and quantity > stock:
        message = f'Only {stock}kg available in stock'
        if request.is_json:
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('main.product_detail', product_id=product_id))

    if min_qty_cfg is not None and quantity < float(min_qty_cfg):
        message = f'Minimum order quantity is {min_qty_cfg}kg'
        if request.is_json:
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('main.product_detail', product_id=product_id))

    if max_qty_cfg is not None and quantity > float(max_qty_cfg):
        message = f'Maximum order quantity is {max_qty_cfg}kg'
        if request.is_json:
            return jsonify({'success': False, 'message': message})
        flash(message, 'error')
        return redirect(url_for('main.product_detail', product_id=product_id))

    # Handle cart storage based on login status
    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(
            user_id=current_user.id,
            product_id=product_id
        ).first()

        if cart_item:
            new_total = cart_item.quantity + quantity
            if stock is not None and new_total > stock:
                message = 'Not enough stock available'
                if request.is_json:
                    return jsonify({'success': False, 'message': message})
                flash(message, 'error')
                return redirect(url_for('main.product_detail', product_id=product_id))
            cart_item.quantity = new_total
        else:
            cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
            db.session.add(cart_item)

        db.session.commit()
    else:
        if 'cart' not in session:
            session['cart'] = {}

        cart = session['cart']
        product_id_str = str(product_id)

        if product_id_str in cart:
            new_total = cart[product_id_str] + quantity
            if stock is not None and new_total > stock:
                message = 'Not enough stock available'
                if request.is_json:
                    return jsonify({'success': False, 'message': message})
                flash(message, 'error')
                return redirect(url_for('main.product_detail', product_id=product_id))
            cart[product_id_str] = new_total
        else:
            cart[product_id_str] = quantity

        session['cart'] = cart
        session.modified = True

    # Return JSON response for AJAX requests
    if request.is_json:
        if current_user.is_authenticated:
            cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
            cart_count = len(cart_items)
            cart_total = sum(item.quantity * item.product.price for item in cart_items)
        else:
            cart = session.get('cart', {})
            cart_count = len(cart)
            cart_total = 0
            for prod_id_str, qty in cart.items():
                prod = Product.query.get(int(prod_id_str))
                if prod:
                    cart_total += qty * prod.price

        qty_display = f'{quantity}kg' if quantity >= 1 else f'{int(quantity * 1000)}g'
        return jsonify({
            'success': True,
            'message': f'{qty_display} added to cart!',
            'cart_count': cart_count,
            'cart_total': cart_total
        })
    else:
        flash('Product added to cart!', 'success')
        return redirect(url_for('main.product_detail', product_id=product_id))


@main_bp.route('/cart')
def cart():
    cart_items = []
    total = 0

    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        for item in cart_items:
            item_price = item.product.price * item.quantity
            total += item_price
    else:
        session_cart = session.get('cart', {})
        for product_id_str, quantity in session_cart.items():
            product = Product.query.get(int(product_id_str))
            if product:
                cart_item = type('CartItem', (), {
                    'product': product,
                    'quantity': quantity,
                    'id': int(product_id_str)
                })()
                cart_items.append(cart_item)
                total += product.price * quantity

    settings = StoreSettings.query.first()
    if settings:
        delivery_charge = 0 if total >= (settings.free_delivery_amount or 0) else (settings.delivery_charge or 0)
    else:
        delivery_charge = 50
    grand_total = total + delivery_charge

    return render_template(
        'cart.html',
        cart_items=cart_items,
        total=total,
        delivery_charge=delivery_charge,
        grand_total=grand_total,
        settings=settings
    )


@main_bp.route('/update_cart', methods=['POST'])
@login_required
def update_cart():
    item_id = request.form.get('item_id', type=int)
    quantity = request.form.get('quantity', type=float)

    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if cart_item and quantity is not None:
        if quantity <= 0:
            db.session.delete(cart_item)
        else:
            # re-check stock if available
            product = cart_item.product
            stock = getattr(product, 'stock_kg', None) or getattr(product, 'stock_quantity', None)
            if stock is not None and quantity > stock:
                flash(f'Not enough stock available (max {stock}).', 'error')
                return redirect(url_for('main.cart'))
            cart_item.quantity = quantity
        db.session.commit()

    return redirect(url_for('main.cart'))


@main_bp.route('/remove_from_cart/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart', 'info')

    return redirect(url_for('main.cart'))

# =========================
# Checkout Routes
# =========================

@main_bp.route('/checkout')
def checkout():
    if not current_user.is_authenticated:
        return redirect(url_for('main.login'))

    # Transfer session cart to DB
    if 'cart' in session and session['cart']:
        session_cart = session['cart']
        for product_id_str, quantity in session_cart.items():
            product_id = int(product_id_str)

            cart_item = CartItem.query.filter_by(
                user_id=current_user.id,
                product_id=product_id
            ).first()

            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
                db.session.add(cart_item)

        session.pop('cart', None)
        db.session.commit()

    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('main.cart'))

    subtotal = sum(item.product.price * item.quantity for item in cart_items)
    gst_amount = sum((item.product.price * item.quantity * (item.product.gst_rate or 0) / 100) for item in cart_items)

    settings = StoreSettings.query.first()
    if settings:
        delivery_charge = 0 if subtotal >= (settings.free_delivery_amount or 0) else (settings.delivery_charge or 0)
    else:
        delivery_charge = 50
    total_amount = subtotal + gst_amount + delivery_charge

    default_address = Address.query.filter_by(user_id=current_user.id, is_default=True).first()

    return render_template(
        'checkout.html',
        cart_items=cart_items,
        subtotal=subtotal,
        gst_amount=gst_amount,
        delivery_charge=delivery_charge,
        total_amount=total_amount,
        default_address=default_address,
        settings=settings
    )


@main_bp.route('/place_order', methods=['POST'])
@login_required
def place_order():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('main.cart'))

    # Delivery details
    delivery_name = request.form.get('delivery_name')
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')
    delivery_city = request.form.get('delivery_city')
    delivery_state = request.form.get('delivery_state')
    delivery_pincode = request.form.get('delivery_pincode')

    subtotal = sum(item.product.price * item.quantity for item in cart_items)
    gst_amount = sum((item.product.price * item.quantity * (item.product.gst_rate or 0) / 100) for item in cart_items)

    settings = StoreSettings.query.first()
    if settings:
        delivery_charge = 0 if subtotal >= (settings.free_delivery_amount or 0) else (settings.delivery_charge or 0)
    else:
        delivery_charge = 50
    total_amount = subtotal + gst_amount + delivery_charge

    order = Order(
        user_id=current_user.id,
        subtotal=subtotal,
        gst_amount=gst_amount,
        delivery_charge=delivery_charge,
        total_amount=total_amount,
        delivery_name=delivery_name,
        delivery_phone=delivery_phone,
        delivery_address=delivery_address,
        delivery_city=delivery_city,
        delivery_state=delivery_state,
        delivery_pincode=delivery_pincode
    )
    order.order_number = order.generate_order_number()

    db.session.add(order)
    db.session.flush()  # get order.id

    # Create order items & reduce stock
    for cart_item in cart_items:
        product = cart_item.product
        stock = getattr(product, 'stock_kg', None)
        if stock is None:
            stock = getattr(product, 'stock_quantity', None)

        if stock is not None:
            if cart_item.quantity > stock:
                flash(f'Insufficient stock for {product.name}. Only {stock}kg available.', 'error')
                return redirect(url_for('main.cart'))
            # persist back to correct field
            if hasattr(product, 'stock_kg'):
                product.stock_kg = stock - cart_item.quantity
            else:
                product.stock_quantity = stock - cart_item.quantity

        order_item = OrderItem(
            order_id=order.id,
            product_id=cart_item.product_id,
            product_name=cart_item.product.name,
            product_name_tamil=cart_item.product.name_tamil,
            product_sku=cart_item.product.sku,
            unit_price=cart_item.product.price,
            price=cart_item.product.price,
            quantity=cart_item.quantity,
            weight_option=getattr(cart_item, 'weight_option', None),
            gst_rate=cart_item.product.gst_rate,
            total_price=cart_item.product.price * cart_item.quantity
        )
        db.session.add(order_item)

    # Clear cart
    for cart_item in cart_items:
        db.session.delete(cart_item)

    db.session.commit()

    # Notifications
    EmailService.send_order_confirmation(order)
    EmailService.send_admin_notification(order, 'new_order')

    flash('Order placed successfully!', 'success')
    return redirect(url_for('main.order_confirmation', order_id=order.id))


@main_bp.route('/order_confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    payment_info = UPIService.get_payment_info(order.total_amount, order.order_number)
    return render_template('order_confirmation.html', order=order, payment_info=payment_info)

# =========================
# User Profile Routes
# =========================

@main_bp.route('/profile')
@login_required
def profile():
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', addresses=addresses)


@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    current_user.first_name = request.form.get('first_name')
    current_user.last_name = request.form.get('last_name')
    current_user.phone = request.form.get('phone')

    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('main.profile'))


@main_bp.route('/add_address', methods=['POST'])
@login_required
def add_address():
    is_default = bool(request.form.get('is_default'))
    if is_default:
        Address.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})

    address = Address(
        user_id=current_user.id,
        name=request.form.get('name'),
        phone=request.form.get('phone'),
        address_line1=request.form.get('address_line1'),
        address_line2=request.form.get('address_line2'),
        city=request.form.get('city'),
        state=request.form.get('state'),
        pincode=request.form.get('pincode'),
        is_default=is_default
    )

    db.session.add(address)
    db.session.commit()

    EmailService.send_admin_notification(None, 'address_change')

    flash('Address added successfully!', 'success')
    return redirect(url_for('main.profile'))


@main_bp.route('/orders')
@login_required
def orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('orders.html', orders=orders)


@main_bp.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template('order_detail.html', order=order)


@main_bp.route('/invoice/<int:order_id>')
@login_required
def invoice(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template('invoice.html', order=order)


@main_bp.route('/invoice/<int:order_id>/pdf')
@login_required
def invoice_pdf(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()

    pdf_data = InvoiceGenerator.generate_invoice_pdf(order)
    if not pdf_data:
        flash('Error generating invoice PDF', 'error')
        return redirect(url_for('main.invoice', order_id=order_id))

    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=invoice_{order.order_number}.pdf'
    return response

# =========================
# Admin Routes
# =========================

@main_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    total_products = Product.query.count()
    total_customers = User.query.filter_by(role='customer').count()

    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    from sqlalchemy import func
    today_sales = db.session.query(func.sum(Order.total_amount)).filter(
        func.date(Order.created_at) == datetime.now().date(),
        Order.payment_status == 'paid'
    ).scalar() or 0

    total_users = User.query.count()
    total_categories = Category.query.count()

    return render_template(
        'admin/dashboard.html',
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_products=total_products,
        total_customers=total_customers,
        total_users=total_users,
        total_categories=total_categories,
        recent_orders=recent_orders,
        today_sales=today_sales
    )

# NEW: Admin Settings landing route (to satisfy admin.admin_settings)
@main_bp.route('/admin/settings')
@login_required
def admin_settings():
    """
    Lightweight landing for Admin Settings. If you don't have a dedicated
    template yet, this safely redirects to the Store Settings page.
    """
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    # If you have a template, use:
    # settings = StoreSettings.query.first()
    # return render_template('admin/settings.html', settings=settings)

    # For now, redirect to an existing settings page:
    return redirect(url_for('main.admin_store_settings'))


@main_bp.route('/admin/products')
@login_required
def admin_products():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    page = request.args.get('page', 1, type=int)
    products = Product.query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    categories = Category.query.all()

    return render_template('admin/products.html', products=products, categories=categories)


@main_bp.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
def admin_add_product():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        product = Product()
        product.name = request.form.get('name')
        product.name_tamil = request.form.get('name_tamil')
        product.description = request.form.get('description')
        product.description_tamil = request.form.get('description_tamil')
        product.category_id = request.form.get('category_id', type=int)
        product.price = request.form.get('price', type=float)
        product.unit = request.form.get('unit')
        product.unit_tamil = request.form.get('unit_tamil')
        # accept stock field posted as stock_quantity
        product.stock_quantity = request.form.get('stock_quantity', type=float)
        product.min_order_quantity = request.form.get('min_order_quantity', type=float)
        product.max_order_quantity = request.form.get('max_order_quantity', type=float)
        product.weight_options = json.dumps(request.form.getlist('weight_options'))
        product.gst_rate = request.form.get('gst_rate', type=float)
        product.is_featured = bool(request.form.get('is_featured'))

        # Handle image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'products')
                os.makedirs(upload_dir, exist_ok=True)

                filename = secure_filename(image_file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                image_path = os.path.join(upload_dir, filename)
                image_file.save(image_path)

                product.image_url = f"/static/uploads/products/{filename}"

        # Image URL fallback
        if not getattr(product, 'image_url', None):
            image_url = request.form.get('image_url')
            if image_url:
                product.image_url = image_url

        product.sku = product.generate_sku()

        db.session.add(product)
        db.session.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('main.admin_products'))

    categories = Category.query.filter_by(is_active=True).all()
    return render_template('admin/add_product.html', categories=categories)


@main_bp.route('/admin/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.name_tamil = request.form.get('name_tamil')
        product.description = request.form.get('description')
        product.description_tamil = request.form.get('description_tamil')
        product.category_id = request.form.get('category_id', type=int)
        product.price = request.form.get('price', type=float)
        product.unit = request.form.get('unit')
        product.unit_tamil = request.form.get('unit_tamil')

        # normalize form -> model fields
        stock_quantity = request.form.get('stock_quantity', type=float)
        if stock_quantity is not None:
            if hasattr(product, 'stock_kg'):
                product.stock_kg = stock_quantity
            else:
                product.stock_quantity = stock_quantity

        min_order_quantity = request.form.get('min_order_quantity', type=float)
        max_order_quantity = request.form.get('max_order_quantity', type=float)
        if min_order_quantity is not None:
            if hasattr(product, 'min_quantity_kg'):
                product.min_quantity_kg = min_order_quantity
            elif hasattr(product, 'min_qty'):
                product.min_qty = min_order_quantity
            else:
                product.min_order_quantity = min_order_quantity
        if max_order_quantity is not None:
            if hasattr(product, 'max_quantity_kg'):
                product.max_quantity_kg = max_order_quantity
            elif hasattr(product, 'max_qty'):
                product.max_qty = max_order_quantity
            else:
                product.max_order_quantity = max_order_quantity

        product.weight_options = json.dumps(request.form.getlist('weight_options'))
        product.gst_rate = request.form.get('gst_rate', type=float)
        product.is_featured = bool(request.form.get('is_featured'))
        product.is_active = bool(request.form.get('is_active'))

        # Handle image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'products')
                os.makedirs(upload_dir, exist_ok=True)

                # Delete old image if stored locally
                if product.image_url and product.image_url.startswith('/static/uploads/'):
                    old_path = current_app.static_folder + product.image_url.replace('/static', '')
                    try:
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        current_app.logger.warning(f"Failed to remove old image: {e}")

                filename = secure_filename(image_file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                image_path = os.path.join(upload_dir, filename)
                image_file.save(image_path)

                product.image_url = f"/static/uploads/products/{filename}"

        elif not request.files.get('image') or not request.files['image'].filename:
            image_url = request.form.get('image_url')
            if image_url and image_url != product.image_url:
                product.image_url = image_url

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('main.admin_products'))

    categories = Category.query.filter_by(is_active=True).all()
    return render_template('admin/edit_product.html', product=product, categories=categories)


# ---- Added: Admin Product Actions (toggle / duplicate / delete / bulk) ----

@main_bp.post('/admin/product/<int:product_id>/toggle')
@login_required
def admin_toggle_product_status(product_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    product = Product.query.get_or_404(product_id)

    new_status_str = (request.form.get('is_active') or '').strip().lower()
    new_status = True if new_status_str == 'true' else False

    product.is_active = new_status
    db.session.commit()

    flash(f'Product {"activated" if product.is_active else "deactivated"} successfully!', 'success')
    return redirect(url_for('main.admin_products'))


@main_bp.post('/admin/product/<int:product_id>/duplicate')
@login_required
def admin_duplicate_product(product_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    product = Product.query.get_or_404(product_id)

    dup = Product(
        name=f'{product.name} (Copy)',
        name_tamil=product.name_tamil,
        description=product.description,
        description_tamil=product.description_tamil,
        category_id=product.category_id,
        price=product.price,
        unit=product.unit,
        unit_tamil=getattr(product, 'unit_tamil', None),
        stock_quantity=getattr(product, 'stock_quantity', None) if hasattr(product, 'stock_quantity') else getattr(product, 'stock_kg', None),
        min_order_quantity=getattr(product, 'min_order_quantity', None) or getattr(product, 'min_quantity_kg', None) or getattr(product, 'min_qty', None),
        max_order_quantity=getattr(product, 'max_order_quantity', None) or getattr(product, 'max_quantity_kg', None) or getattr(product, 'max_qty', None),
        weight_options=product.weight_options,
        gst_rate=product.gst_rate,
        image_url=product.image_url,
        is_featured=product.is_featured,
        is_active=False,
    )
    dup.sku = dup.generate_sku()

    db.session.add(dup)
    db.session.commit()

    flash('Product duplicated successfully!', 'success')
    return redirect(url_for('main.admin_products'))


@main_bp.post('/admin/product/<int:product_id>/delete')
@login_required
def admin_delete_product(product_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    product = Product.query.get_or_404(product_id)

    db.session.delete(product)
    db.session.commit()

    flash('Product deleted successfully!', 'success')
    return redirect(url_for('main.admin_products'))


@main_bp.post('/admin/products/bulk')
@login_required
def admin_products_bulk_action():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    action = request.form.get('action')
    try:
        ids_raw = request.form.get('product_ids') or '[]'
        product_ids = json.loads(ids_raw)
        product_ids = [int(x) for x in product_ids]
    except Exception:
        flash('Invalid product selection.', 'error')
        return redirect(url_for('main.admin_products'))

    if not product_ids:
        flash('No products selected.', 'warning')
        return redirect(url_for('main.admin_products'))

    q = Product.query.filter(Product.id.in_(product_ids))

    if action == 'activate':
        updated = q.update({Product.is_active: True}, synchronize_session=False)
        db.session.commit()
        flash(f'Activated {updated} products.', 'success')
    elif action == 'deactivate':
        updated = q.update({Product.is_active: False}, synchronize_session=False)
        db.session.commit()
        flash(f'Deactivated {updated} products.', 'success')
    elif action == 'delete':
        deleted = 0
        for p in q.all():
            db.session.delete(p)
            deleted += 1
        db.session.commit()
        flash(f'Deleted {deleted} products.', 'success')
    else:
        flash('Unknown bulk action.', 'error')

    return redirect(url_for('main.admin_products'))

# ------------------------


@main_bp.route('/admin/orders')
@login_required
def admin_orders():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')

    query = Order.query
    if status:
        query = query.filter_by(status=status)

    orders = query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('admin/orders.html', orders=orders, selected_status=status)


@main_bp.route('/admin/orders/<int:order_id>/update_status', methods=['POST'])
@login_required
def admin_update_order_status(order_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')

    if new_status not in ['pending', 'confirmed', 'processing', 'packed', 'shipped', 'delivered', 'cancelled']:
        flash('Invalid status', 'error')
        return redirect(url_for('main.admin_orders'))

    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.now()

    db.session.commit()

    # Email notification
    try:
        from utils.email_sender import send_order_status_update_email
        send_order_status_update_email(order, old_status, new_status)
    except Exception as e:
        logging.warning(f"Failed to send status update email: {str(e)}")

    # Invoice generation on delivered
    if new_status == 'delivered' and old_status != 'delivered':
        try:
            from utils.invoice_generator import generate_invoice
            generate_invoice(order.id)
            flash(f'Order #{order.id} marked as delivered and invoice generated!', 'success')
        except Exception as e:
            flash(f'Order status updated but invoice generation failed: {str(e)}', 'warning')
    else:
        flash(f'Order #{order.id} status updated to {new_status}!', 'success')

    return redirect(url_for('main.admin_orders'))


@main_bp.route('/admin/orders/<int:order_id>/invoice')
@login_required
def admin_download_invoice(order_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    order = Order.query.get_or_404(order_id)

    try:
        from utils.invoice_generator import generate_invoice
        invoice_path = generate_invoice(order_id)
        return send_file(invoice_path, as_attachment=True, download_name=f'invoice_{order.id}.pdf')
    except Exception as e:
        flash(f'Error generating invoice: {str(e)}', 'error')
        return redirect(url_for('main.admin_orders'))


@main_bp.route('/admin/orders/<int:order_id>/resend_email', methods=['POST'])
@login_required
def admin_resend_order_email(order_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    order = Order.query.get_or_404(order_id)

    try:
        from utils.email_sender import send_order_confirmation_email
        send_order_confirmation_email(order)
        flash(f'Order confirmation email resent to {order.customer_email}!', 'success')
    except Exception as e:
        flash(f'Error sending email: {str(e)}', 'error')

    return redirect(url_for('main.admin_orders'))


@main_bp.route('/admin/orders/<int:order_id>/view')
@login_required
def admin_view_order(order_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    order = Order.query.get_or_404(order_id)
    order_items = OrderItem.query.filter_by(order_id=order_id).all()

    return render_template('admin/view_order.html', order=order, order_items=order_items)

# =========================
# Customer Order Tracking
# =========================

@main_bp.route('/track/<int:order_id>')
def track_order(order_id):
    order = Order.query.get_or_404(order_id)
    order_items = OrderItem.query.filter_by(order_id=order_id).all()

    status_timeline = [
        {'status': 'pending', 'label': 'Order Placed', 'completed': True, 'date': order.created_at},
        {'status': 'confirmed', 'label': 'Order Confirmed',
         'completed': order.status in ['confirmed', 'processing', 'packed', 'shipped', 'delivered'],
         'date': getattr(order, 'confirmed_at', None)},
        {'status': 'processing', 'label': 'Processing',
         'completed': order.status in ['processing', 'packed', 'shipped', 'delivered'],
         'date': getattr(order, 'processing_at', None)},
        {'status': 'packed', 'label': 'Packed', 'completed': order.status in ['packed', 'shipped', 'delivered'],
         'date': getattr(order, 'packed_at', None)},
        {'status': 'shipped', 'label': 'Shipped', 'completed': order.status in ['shipped', 'delivered'],
         'date': getattr(order, 'shipped_at', None)},
        {'status': 'delivered', 'label': 'Delivered', 'completed': order.status == 'delivered',
         'date': getattr(order, 'delivered_at', None)}
    ]

    settings = StoreSettings.query.first()
    return render_template(
        'track_order.html',
        order=order,
        order_items=order_items,
        status_timeline=status_timeline,
        settings=settings
    )

# =========================
# Communications
# =========================

@main_bp.route('/admin/communications')
@login_required
def admin_communications():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()

    return render_template('admin/communications.html', settings=settings, campaigns=campaigns)


@main_bp.route('/admin/update-email-settings', methods=['POST'])
@login_required
def admin_update_email_settings():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)

    settings.smtp_server = request.form.get('smtp_server')
    settings.smtp_port = int(request.form.get('smtp_port', 587))
    settings.smtp_username = request.form.get('smtp_username')
    settings.smtp_password = request.form.get('smtp_password')
    settings.smtp_use_tls = 'smtp_use_tls' in request.form
    settings.email_notifications_enabled = 'email_notifications_enabled' in request.form

    db.session.commit()
    flash('Email settings updated successfully!', 'success')
    return redirect(url_for('main.admin_communications'))


@main_bp.route('/admin/update-whatsapp-settings', methods=['POST'])
@login_required
def admin_update_whatsapp_settings():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)

    settings.twilio_account_sid = request.form.get('twilio_account_sid')
    settings.twilio_auth_token = request.form.get('twilio_auth_token')
    settings.whatsapp_number = request.form.get('whatsapp_number')
    settings.whatsapp_enabled = 'whatsapp_enabled' in request.form

    db.session.commit()
    flash('WhatsApp settings updated successfully!', 'success')
    return redirect(url_for('main.admin_communications'))


@main_bp.route('/admin/create-campaign', methods=['POST'])
@login_required
def admin_create_campaign():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    campaign = Campaign(
        name=request.form.get('campaign_name'),
        type=request.form.get('campaign_type'),
        target_audience=request.form.get('target_audience'),
        subject=request.form.get('campaign_subject'),
        message=request.form.get('campaign_message'),
        created_by=current_user.id
    )

    if 'send_immediately' in request.form:
        campaign.status = 'sent'
        campaign.sent_at = datetime.utcnow()
        # TODO: send immediately
    elif request.form.get('scheduled_time'):
        campaign.status = 'scheduled'
        campaign.scheduled_time = datetime.strptime(request.form.get('scheduled_time'), '%Y-%m-%dT%H:%M')

    db.session.add(campaign)
    db.session.commit()

    flash('Campaign created successfully!', 'success')
    return redirect(url_for('main.admin_communications'))


@csrf.exempt
@main_bp.route('/admin/test-email', methods=['POST'])
@login_required
def admin_test_email():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        from utils.email_sender import send_test_email

        settings = StoreSettings.query.first()
        if not settings or not settings.smtp_server:
            return jsonify({'success': False, 'error': 'SMTP settings not configured'})

        send_test_email(settings, current_user.email)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@csrf.exempt
@main_bp.route('/admin/test-whatsapp', methods=['POST'])
@login_required
def admin_test_whatsapp():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        from utils.whatsapp_service import send_test_message

        settings = StoreSettings.query.first()
        if not settings or not settings.twilio_account_sid:
            return jsonify({'success': False, 'error': 'WhatsApp settings not configured'})

        send_test_message(settings)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# =========================
# Settings & Homepage
# =========================

@main_bp.route('/admin/update-invoice-settings', methods=['POST'])
@login_required
def admin_update_invoice_settings():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)

    # Invoice logo settings
    settings.invoice_logo_url = request.form.get('invoice_logo_url')
    settings.invoice_logo_position = request.form.get('invoice_logo_position', 'left')
    settings.invoice_logo_size = int(request.form.get('invoice_logo_size', 80))

    # Invoice UPI logo settings
    settings.invoice_upi_logo_url = request.form.get('invoice_upi_logo_url')
    settings.invoice_upi_logo_position = request.form.get('invoice_upi_logo_position', 'center')
    settings.invoice_upi_logo_size = int(request.form.get('invoice_upi_logo_size', 150))

    try:
        db.session.commit()
        current_app.logger.info(
            f"Invoice settings updated: logo={settings.invoice_logo_url}, upi_logo={settings.invoice_upi_logo_url}")
        flash('Invoice logo settings updated successfully!', 'success')
        return redirect(url_for('main.admin_invoice_logos'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating invoice settings: {e}")
        flash(f'Error saving invoice settings: {str(e)}', 'error')
        return redirect(url_for('main.admin_invoice_logos'))


@main_bp.route('/admin/update-templates', methods=['POST'])
@login_required
def admin_update_templates():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)

    settings.order_email_subject = request.form.get('order_email_subject')
    settings.order_whatsapp_template = request.form.get('order_whatsapp_template')
    settings.delivery_whatsapp_template = request.form.get('delivery_whatsapp_template')
    settings.marketing_whatsapp_template = request.form.get('marketing_whatsapp_template')

    db.session.commit()
    flash('Message templates updated successfully!', 'success')
    return redirect(url_for('main.admin_communications'))


@main_bp.route('/admin/homepage-settings')
@login_required
def admin_homepage_settings():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    return render_template('admin/homepage_settings.html', settings=settings)


@main_bp.route('/admin/update-homepage-settings', methods=['POST'])
@login_required
def admin_update_homepage_settings():
    if current_user.role != 'admin':
        return redirect(url_for('main.login'))

    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)

    # Store information
    settings.store_name = request.form.get('store_name')
    settings.store_name_tamil = request.form.get('store_name_tamil')
    settings.tagline = request.form.get('tagline')
    settings.tagline_tamil = request.form.get('tagline_tamil')
    settings.logo_url = request.form.get('logo_url')
    settings.address = request.form.get('address')
    settings.phone = request.form.get('phone')
    settings.email = request.form.get('email')
    settings.website = request.form.get('website')

    # Homepage content
    settings.hero_image_url = request.form.get('hero_image_url')
    settings.hero_subtitle = request.form.get('hero_subtitle')
    settings.hero_description = request.form.get('hero_description')
    settings.categories_title = request.form.get('categories_title')
    settings.categories_subtitle = request.form.get('categories_subtitle')

    # Delivery settings
    settings.free_delivery_amount = float(request.form.get('free_delivery_amount', 500))
    settings.delivery_charge = float(request.form.get('delivery_charge', 50))

    # Payment settings
    settings.upi_id = request.form.get('upi_id')
    settings.upi_qr_image_url = request.form.get('upi_qr_image_url')

    try:
        db.session.commit()
        current_app.logger.info(
            f"Homepage settings updated: store_name={settings.store_name}, upi_id={settings.upi_id}")

        try:
            send_settings_update_notification(settings)
        except Exception as email_error:
            current_app.logger.warning(f"Failed to send email notification: {email_error}")

        flash('Homepage settings updated successfully! Changes are now live on your homepage.', 'success')
        return redirect(url_for('main.admin_homepage_settings'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating homepage settings: {e}")
        flash(f'Error saving settings: {str(e)}', 'error')
        return redirect(url_for('main.admin_homepage_settings'))

# =========================
# Email Notification Helper
# =========================

def send_settings_update_notification(settings):
    """Send email notification when homepage settings are updated"""
    try:
        from flask_mail import Message

        admin_users = User.query.filter_by(role='admin').all()

        for admin in admin_users:
            if not admin.email:
                continue

            msg = Message(
                subject=f"Homepage Settings Updated - {settings.store_name or 'Thaavaram'}",
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[admin.email]
            )

            # Plain text
            msg.body = f"""
Homepage Settings Updated

Store Name: {settings.store_name or 'Not set'}
Store Name (Tamil): {settings.store_name_tamil or 'Not set'}
Tagline: {settings.tagline or 'Not set'}
Hero Subtitle: {settings.hero_subtitle or 'Not set'}

Payment Settings:
UPI ID: {settings.upi_id or 'Not set'}
UPI QR Image URL: {settings.upi_qr_image_url or 'Not set'}

Delivery Settings:
Free Delivery Above: ₹{settings.free_delivery_amount or 500}
Standard Delivery Charge: ₹{settings.delivery_charge or 50}

Contact Information:
Phone: {settings.phone or 'Not set'}
Email: {settings.email or 'Not set'}
Address: {settings.address or 'Not set'}

Updated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Visit your store: {request.host_url}
Admin Panel: {request.host_url}admin
            """.strip()

            # HTML version
            msg.html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4CAF50; border-bottom: 2px solid #4CAF50; padding-bottom: 10px;">
            Homepage Settings Updated
        </h2>

        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #333; margin-top: 0;">Store Information</h3>
            <p><strong>Store Name:</strong> {settings.store_name or 'Not set'}</p>
            <p><strong>Store Name (Tamil):</strong> {settings.store_name_tamil or 'Not set'}</p>
            <p><strong>Tagline:</strong> {settings.tagline or 'Not set'}</p>
            <p><strong>Hero Subtitle:</strong> {settings.hero_subtitle or 'Not set'}</p>
        </div>

        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #333; margin-top: 0;">Payment Settings</h3>
            <p><strong>UPI ID:</strong> {settings.upi_id or 'Not set'}</p>
            <p><strong>UPI QR Image URL:</strong> {settings.upi_qr_image_url or 'Not set'}</p>
        </div>

        <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #333; margin-top: 0;">Delivery Settings</h3>
            <p><strong>Free Delivery Above:</strong> ₹{settings.free_delivery_amount or 500}</p>
            <p><strong>Standard Delivery Charge:</strong> ₹{settings.delivery_charge or 50}</p>
        </div>

        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #333; margin-top: 0;">Contact Information</h3>
            <p><strong>Phone:</strong> {settings.phone or 'Not set'}</p>
            <p><strong>Email:</strong> {settings.email or 'Not set'}</p>
            <p><strong>Address:</strong> {settings.address or 'Not set'}</p>
        </div>

        <div style="margin: 30px 0; text-align: center;">
            <a href="{request.host_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px;">View Store</a>
            <a href="{request.host_url}admin" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Admin Panel</a>
        </div>

        <p style="color: #666; font-size: 12px; text-align: center; margin-top: 30px;">
            Updated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
            """.strip()

            try:
                mail.send(msg)
                current_app.logger.info(f"Settings update notification sent to {admin.email}")
            except Exception as e:
                current_app.logger.error(f"Failed to send settings notification to {admin.email}: {e}")

    except Exception as e:
        current_app.logger.error(f"Failed to send settings notification: {e}")
        raise

# =========================
# Store Settings
# =========================

@main_bp.route('/admin/store-settings', methods=['GET', 'POST'])
@login_required
def admin_store_settings():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    settings = StoreSettings.query.first()

    if request.method == 'POST':
        if not settings:
            settings = StoreSettings()
            db.session.add(settings)

        # Update store settings from form
        settings.store_name = request.form.get('store_name')
        settings.store_name_tamil = request.form.get('store_name_tamil')
        settings.tagline = request.form.get('tagline')
        settings.tagline_tamil = request.form.get('tagline_tamil')
        settings.description = request.form.get('description')
        settings.address = request.form.get('address')
        settings.phone = request.form.get('phone')
        settings.email = request.form.get('email')
        settings.gst_number = request.form.get('gst_number')
        settings.upi_id = request.form.get('upi_id')
        settings.bank_name = request.form.get('bank_name')
        settings.bank_account_name = request.form.get('bank_account_name')
        settings.bank_account_number = request.form.get('bank_account_number')
        settings.bank_ifsc = request.form.get('bank_ifsc')
        settings.theme_color = request.form.get('theme_color')
        settings.delivery_charge = float(request.form.get('delivery_charge', 0) or 0)
        settings.free_delivery_amount = float(request.form.get('free_delivery_amount', 0) or 0)

        # Handle logo upload (simplified)
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                upload_dir = os.path.join(current_app.static_folder, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(logo_file.filename)}"
                path = os.path.join(upload_dir, filename)
                logo_file.save(path)
                settings.logo_url = f"/static/uploads/{filename}"

        db.session.commit()
        flash('Store settings updated successfully!', 'success')
        return redirect(url_for('main.admin_store_settings'))

    return render_template('admin/store_settings.html', settings=settings)

# =========================
# Template Editor
# =========================

@main_bp.route('/admin/template-editor', methods=['GET', 'POST'])
@login_required
def admin_template_editor():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    settings = StoreSettings.query.first()

    if request.method == 'POST':
        if not settings:
            settings = StoreSettings()
            db.session.add(settings)

        settings.hero_title = request.form.get('hero_title')
        settings.hero_title_tamil = request.form.get('hero_title_tamil')
        settings.hero_subtitle = request.form.get('hero_subtitle')
        settings.hero_subtitle_tamil = request.form.get('hero_subtitle_tamil')
        settings.layout_style = request.form.get('layout_style')
        settings.primary_color = request.form.get('primary_color')
        settings.secondary_color = request.form.get('secondary_color')
        settings.accent_color = request.form.get('accent_color')
        settings.text_color = request.form.get('text_color')
        settings.background_color = request.form.get('background_color')
        settings.custom_css = request.form.get('custom_css')

        db.session.commit()
        flash('Template settings updated successfully!', 'success')
        return redirect(url_for('main.admin_template_editor'))

    return render_template('admin/template_editor.html', settings=settings)

# =========================
# Categories Admin
# =========================

@main_bp.route('/admin/categories')
@login_required
def admin_categories():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    categories = Category.query.order_by(Category.sort_order).all()
    return render_template('admin/categories.html', categories=categories)


@main_bp.route('/admin/categories/add', methods=['POST'])
@login_required
def admin_add_category():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    name = request.form.get('name')
    name_tamil = request.form.get('name_tamil')
    description = request.form.get('description')
    sort_order = request.form.get('sort_order', type=int) or 1
    is_active = bool(request.form.get('is_active'))

    if not name:
        flash('Category name is required', 'error')
        return redirect(url_for('main.admin_categories'))

    existing = Category.query.filter_by(name=name).first()
    if existing:
        flash('Category with this name already exists', 'error')
        return redirect(url_for('main.admin_categories'))

    category = Category(
        name=name,
        name_tamil=name_tamil or name,
        description=description,
        sort_order=sort_order,
        is_active=is_active
    )
    db.session.add(category)
    db.session.commit()

    flash('Category added successfully!', 'success')
    return redirect(url_for('main.admin_categories'))


@main_bp.route('/admin/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_category(category_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        category.name = request.form.get('name')
        category.name_tamil = request.form.get('name_tamil')
        category.description = request.form.get('description')
        category.sort_order = request.form.get('sort_order', type=int)
        category.is_active = bool(request.form.get('is_active'))

        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('main.admin_categories'))

    return render_template('admin/edit_category.html', category=category)


@main_bp.route('/admin/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def admin_delete_category(category_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    category = Category.query.get_or_404(category_id)

    products_count = Product.query.filter_by(category_id=category_id).count()
    if products_count > 0:
        flash(f'Cannot delete category. It has {products_count} products assigned to it.', 'error')
        return redirect(url_for('main.admin_categories'))

    db.session.delete(category)
    db.session.commit()

    flash('Category deleted successfully!', 'success')
    return redirect(url_for('main.admin_categories'))


@main_bp.route('/admin/categories/<int:category_id>/toggle', methods=['POST'])
@login_required
def admin_toggle_category(category_id):
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    category = Category.query.get_or_404(category_id)
    category.is_active = not category.is_active
    db.session.commit()

    status = 'activated' if category.is_active else 'deactivated'
    flash(f'Category {status} successfully!', 'success')
    return redirect(url_for('main.admin_categories'))

# =========================
# Users Admin
# =========================

@main_bp.route('/admin/users')
@login_required
def admin_users():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users)


@main_bp.route('/admin/user/add', methods=['POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))

    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    if User.query.filter_by(email=email).first():
        flash('Email already registered', 'error')
        return redirect(url_for('main.admin_users'))

    user = User(username=username, email=email, role=role)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    flash('User added successfully!', 'success')
    return redirect(url_for('main.admin_users'))

# =========================
# Error handlers & Context
# =========================

@main_bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@main_bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


@main_bp.app_context_processor
def inject_cart_count():
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    return dict(cart_count=cart_count)


@main_bp.app_context_processor
def inject_settings():
    settings = StoreSettings.query.first()
    return dict(store_settings=settings)

# =========================
# URL Helper (smart url_for for templates)
# =========================

def smart_url_for(endpoint: str, **values):
    """
    More forgiving url_for used inside Jinja:
    - Tries the endpoint as given.
    - If it starts with 'admin.' try 'main.' + same endpoint.
    - Otherwise, try 'main.' + endpoint.
    """
    try:
        return url_for(endpoint, **values)
    except Exception:
        pass
    if endpoint.startswith('admin.'):
        try:
            return url_for(f"main.{endpoint}", **values)
        except Exception:
            # also try stripping the 'admin.' if some aliases registered that way
            try:
                return url_for(f"main.{endpoint.split('admin.',1)[1]}", **values)
            except Exception:
                pass
    try:
        return url_for(f"main.{endpoint}", **values)
    except Exception:
        # last resort: bubble the original error for clarity
        return url_for(endpoint, **values)

@main_bp.record_once
def _wire_smart_url_for(state):
    # Make Jinja 'url_for' point to our smarter version (template-only).
    state.app.jinja_env.globals['url_for'] = smart_url_for

# =========================
# Endpoint Aliases
# =========================

@main_bp.record_once
def register_endpoint_aliases(state):
    """
    Create global and admin-prefixed endpoint aliases so templates that call
    url_for('products') or url_for('admin.admin_products') continue to work.
    Also adds alias for 'add_to_cart' so url_for('add_to_cart') resolves.
    """
    app = state.app

    def alias(src_endpoint: str, alias_endpoint: str, rule: str):
        # Find allowed methods from existing rules for the source endpoint
        methods = set()
        for r in app.url_map.iter_rules():
            if r.endpoint == src_endpoint:
                if r.methods:
                    methods.update(m for m in r.methods if m not in {'HEAD', 'OPTIONS'})
        src_view = app.view_functions.get(src_endpoint)
        if not src_view:
            return
        try:
            app.add_url_rule(rule, endpoint=alias_endpoint, view_func=src_view,
                             methods=sorted(methods) if methods else None)
        except Exception:
            # Already exists or conflict; ignore
            pass

    # Public/global aliases (let templates use url_for('products'), etc.)
    alias('main.products',        'products',        '/products')
    alias('main.product_detail',  'product_detail',  '/product/<int:product_id>')
    alias('main.cart',            'cart',            '/cart')
    alias('main.checkout',        'checkout',        '/checkout')
    alias('main.add_to_cart',     'add_to_cart',     '/add_to_cart')
    alias('main.update_cart',     'update_cart',     '/update_cart')
    alias('main.remove_from_cart','remove_from_cart','/remove_from_cart/<int:item_id>')
    alias('main.place_order',     'place_order',     '/place_order')
    alias('main.order_confirmation','order_confirmation','/order_confirmation/<int:order_id>')

    # Admin aliases so templates can use url_for('admin.xxx')
    alias('main.admin_dashboard',               'admin.admin_dashboard',              '/admin')
    alias('main.admin_settings',                'admin.admin_settings',               '/admin/settings')
    alias('main.admin_products',                'admin.admin_products',               '/admin/products')
    alias('main.admin_add_product',             'admin.admin_add_product',            '/admin/product/add')
    alias('main.admin_edit_product',            'admin.admin_edit_product',           '/admin/product/<int:product_id>/edit')
    alias('main.admin_toggle_product_status',   'admin.admin_toggle_product_status',  '/admin/product/<int:product_id>/toggle')
    alias('main.admin_duplicate_product',       'admin.admin_duplicate_product',      '/admin/product/<int:product_id>/duplicate')
    alias('main.admin_delete_product',          'admin.admin_delete_product',         '/admin/product/<int:product_id>/delete')
    alias('main.admin_products_bulk_action',    'admin.admin_products_bulk_action',   '/admin/products/bulk')

    alias('main.admin_orders',                  'admin.admin_orders',                 '/admin/orders')
    alias('main.admin_update_order_status',     'admin.admin_update_order_status',    '/admin/orders/<int:order_id>/update_status')
    alias('main.admin_download_invoice',        'admin.admin_download_invoice',       '/admin/orders/<int:order_id>/invoice')
    alias('main.admin_resend_order_email',      'admin.admin_resend_order_email',     '/admin/orders/<int:order_id>/resend_email')
    alias('main.admin_view_order',              'admin.admin_view_order',             '/admin/orders/<int:order_id>/view')

    alias('main.admin_categories',              'admin.admin_categories',             '/admin/categories')
    alias('main.admin_add_category',            'admin.admin_add_category',           '/admin/categories/add')
    alias('main.admin_edit_category',           'admin.admin_edit_category',          '/admin/categories/<int:category_id>/edit')
    alias('main.admin_delete_category',         'admin.admin_delete_category',        '/admin/categories/<int:category_id>/delete')
    alias('main.admin_toggle_category',         'admin.admin_toggle_category',        '/admin/categories/<int:category_id>/toggle')

    alias('main.admin_users',                   'admin.admin_users',                  '/admin/users')
    alias('main.admin_add_user',                'admin.admin_add_user',               '/admin/user/add')

    alias('main.admin_communications',          'admin.admin_communications',         '/admin/communications')
    alias('main.admin_update_email_settings',   'admin.admin_update_email_settings',  '/admin/update-email-settings')
    alias('main.admin_update_whatsapp_settings','admin.admin_update_whatsapp_settings','/admin/update-whatsapp-settings')
    alias('main.admin_create_campaign',         'admin.admin_create_campaign',        '/admin/create-campaign')
    alias('main.admin_test_email',              'admin.admin_test_email',             '/admin/test-email')
    alias('main.admin_test_whatsapp',           'admin.admin_test_whatsapp',          '/admin/test-whatsapp')

    alias('main.admin_invoice_logos',           'admin.admin_invoice_logos',          '/admin/invoice-logos')
    alias('main.admin_update_invoice_logos',    'admin.admin_update_invoice_logos',   '/admin/update-invoice-logos')
    alias('main.admin_update_invoice_settings', 'admin.admin_update_invoice_settings','/admin/update-invoice-settings')

    alias('main.admin_homepage_settings',       'admin.admin_homepage_settings',      '/admin/homepage-settings')
    alias('main.admin_update_homepage_settings','admin.admin_update_homepage_settings','/admin/update-homepage-settings')

    alias('main.admin_store_settings',          'admin.admin_store_settings',         '/admin/store-settings')
    alias('main.admin_template_editor',         'admin.admin_template_editor',        '/admin/template-editor')
    alias('main.admin_update_templates',        'admin.admin_update_templates',       '/admin/update-templates')
