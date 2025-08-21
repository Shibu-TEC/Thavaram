from extensions import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import string
import random

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default='customer')  # customer, storekeeper, admin
    _is_active = db.Column('is_active', db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def is_active(self):
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        self._is_active = value
    
    # Customer specific fields
    addresses = db.relationship('Address', backref='user', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_storekeeper(self):
        return self.role in ['admin', 'storekeeper']

class Address(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address_line1 = db.Column(db.Text, nullable=False)
    address_line2 = db.Column(db.Text)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_tamil = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    name_tamil = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    description_tamil = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)  # Price per kg
    stock_kg = db.Column(db.Float, default=100.0)  # Stock in kg
    min_quantity_kg = db.Column(db.Float, default=0.25)  # Minimum 250g
    max_quantity_kg = db.Column(db.Float, default=5.0)   # Maximum 5kg
    quantity_step_kg = db.Column(db.Float, default=0.25) # 250g increments
    unit = db.Column(db.String(20), default='kg')  # kg, grams, pieces, liters
    unit_tamil = db.Column(db.String(20), default='கிலோ')
    stock_quantity = db.Column(db.Float, default=0)
    min_order_quantity = db.Column(db.Float, default=0.5)
    max_order_quantity = db.Column(db.Float, default=10)
    weight_options = db.Column(db.Text)  # JSON string for weight options
    image_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    gst_rate = db.Column(db.Float, default=0)  # GST percentage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def generate_sku(self):
        """Generate unique SKU for product"""
        prefix = 'THV'
        category = Category.query.get(self.category_id)
        if category:
            cat_code = ''.join([c.upper() for c in category.name.split()[:2]])[:3]
            prefix += cat_code
        
        # Generate random number
        while True:
            random_num = ''.join(random.choices(string.digits, k=4))
            sku = f"{prefix}{random_num}"
            if not Product.query.filter_by(sku=sku).first():
                return sku

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    weight_option = db.Column(db.String(50))  # Selected weight option
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product', backref='cart_items')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Order details
    subtotal = db.Column(db.Float, nullable=False)
    gst_amount = db.Column(db.Float, default=0)
    delivery_charge = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    
    # Delivery details
    delivery_name = db.Column(db.String(100), nullable=False)
    delivery_phone = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)
    delivery_city = db.Column(db.String(50), nullable=False)
    delivery_state = db.Column(db.String(50), nullable=False)
    delivery_pincode = db.Column(db.String(10), nullable=False)
    
    # Order status
    status = db.Column(db.String(20), default='pending')  # pending, accepted, packing, packed, shipped, delivered, cancelled
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed
    payment_method = db.Column(db.String(20), default='upi')
    
    # Tracking
    tracking_number = db.Column(db.String(100))
    tracking_url = db.Column(db.String(255))
    delivery_partner = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)
    packed_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def generate_order_number(self):
        """Generate unique order number"""
        prefix = 'THV'
        date_str = datetime.now().strftime('%Y%m%d')
        
        # Get count of orders today
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = Order.query.filter(Order.created_at >= today_start).count()
        
        return f"{prefix}{date_str}{today_count + 1:04d}"

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    # Product details at time of order
    product_name = db.Column(db.String(200), nullable=False)
    product_name_tamil = db.Column(db.String(200))
    product_sku = db.Column(db.String(20))
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50))
    gst_rate = db.Column(db.Float, default=0)
    
    product = db.relationship('Product', backref='order_items')

class StoreSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Store information
    store_name = db.Column(db.String(100), default='Thaavaram')
    store_name_tamil = db.Column(db.String(100), default='தாவரம்')
    tagline = db.Column(db.String(200))
    tagline_tamil = db.Column(db.String(200))
    logo_url = db.Column(db.String(255))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(100))
    
    # Business details
    gst_number = db.Column(db.String(20))
    
    # Bank details
    bank_name = db.Column(db.String(100))
    bank_account_name = db.Column(db.String(100))
    bank_account_number = db.Column(db.String(30))
    bank_ifsc = db.Column(db.String(15))
    
    # UPI details
    upi_id = db.Column(db.String(100))
    upi_qr_image_url = db.Column(db.String(255))  # UPI QR code image
    
    # Delivery settings
    free_delivery_amount = db.Column(db.Float, default=500)
    delivery_charge = db.Column(db.Float, default=50)
    
    # Email settings
    smtp_server = db.Column(db.String(100))
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(120))
    smtp_password = db.Column(db.String(200))
    smtp_use_tls = db.Column(db.Boolean, default=True)
    
    # WhatsApp settings
    whatsapp_number = db.Column(db.String(20))
    whatsapp_api_key = db.Column(db.String(200))
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    
    # Automatic notifications
    email_notifications_enabled = db.Column(db.Boolean, default=True)
    sms_notifications_enabled = db.Column(db.Boolean, default=False)
    
    # Invoice settings
    invoice_header = db.Column(db.String(100), default='TAX INVOICE')
    invoice_prefix = db.Column(db.String(10), default='THV')
    invoice_footer = db.Column(db.String(200), default='Thank you for your business!')
    
    # Invoice logo settings
    invoice_logo_url = db.Column(db.String(255))  # Company logo for invoices
    invoice_logo_position = db.Column(db.String(20), default='left')  # left, center, right
    invoice_logo_size = db.Column(db.Integer, default=80)  # Height in pixels
    
    # Invoice UPI logo settings  
    invoice_upi_logo_url = db.Column(db.String(255))  # UPI logo for payment section
    invoice_upi_logo_position = db.Column(db.String(20), default='center')  # left, center, right
    invoice_upi_logo_size = db.Column(db.Integer, default=150)  # Height in pixels
    
    # Homepage content settings
    hero_image_url = db.Column(db.String(255))
    hero_subtitle = db.Column(db.String(255))
    hero_description = db.Column(db.Text)
    categories_title = db.Column(db.String(255), default='Shop by Categories')
    categories_subtitle = db.Column(db.String(255), default='வகைகள் மூலம் வாங்குங்கள்')
    
    # Twilio/WhatsApp settings
    twilio_account_sid = db.Column(db.String(100))
    twilio_auth_token = db.Column(db.String(100))
    
    # Message templates
    order_email_subject = db.Column(db.String(200), default='Order Confirmation - #{order_id}')
    order_whatsapp_template = db.Column(db.Text, default='Hi {customer_name}, your order #{order_id} has been confirmed! Total: ₹{total_amount}. Track: {tracking_url}')
    delivery_whatsapp_template = db.Column(db.Text, default='Hi {customer_name}, your order #{order_id} is {status}! Track: {tracking_url}')
    marketing_whatsapp_template = db.Column(db.Text, default='Hi {customer_name}, check out our fresh organic products! Visit: {website_url}')

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # email, whatsapp, both
    target_audience = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, sent, scheduled
    recipients_count = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_time = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Theme settings
    theme_color = db.Column(db.String(10), default='#28a745')
    
    # Terms and conditions
    terms_and_conditions = db.Column(db.Text)
    privacy_policy = db.Column(db.Text)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NotificationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    notification_type = db.Column(db.String(20), nullable=False)  # email, whatsapp
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    
    order = db.relationship('Order', backref='notifications')
