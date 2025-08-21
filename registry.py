"""
Registry for all application components and utilities
"""

# Category constants
CATEGORIES = {
    'vegetables': {
        'name': 'Vegetables',
        'name_tamil': 'காய்கறிகள்',
        'icon': 'fas fa-carrot'
    },
    'fruits': {
        'name': 'Fruits',
        'name_tamil': 'பழங்கள்',
        'icon': 'fas fa-apple-alt'
    },
    'grains': {
        'name': 'Grains & Cereals',
        'name_tamil': 'தானியங்கள்',
        'icon': 'fas fa-seedling'
    },
    'spices': {
        'name': 'Spices & Herbs',
        'name_tamil': 'மசாலா & மூலிகைகள்',
        'icon': 'fas fa-pepper-hot'
    },
    'dairy': {
        'name': 'Dairy Products',
        'name_tamil': 'பால் பொருட்கள்',
        'icon': 'fas fa-cheese'
    },
    'oils': {
        'name': 'Oils & Ghee',
        'name_tamil': 'எண்ணெய் & நெய்',
        'icon': 'fas fa-oil-can'
    }
}

# Units
UNITS = {
    'kg': {'name': 'Kilogram', 'name_tamil': 'கிலோ', 'symbol': 'kg'},
    'grams': {'name': 'Grams', 'name_tamil': 'கிராம்', 'symbol': 'g'},
    'pieces': {'name': 'Pieces', 'name_tamil': 'துண்டுகள்', 'symbol': 'pcs'},
    'liters': {'name': 'Liters', 'name_tamil': 'லிட்டர்', 'symbol': 'L'},
    'bundles': {'name': 'Bundles', 'name_tamil': 'கட்டுகள்', 'symbol': 'bundles'}
}

# Order status
ORDER_STATUS = {
    'pending': {'name': 'Order Placed', 'name_tamil': 'ஆர்டர் பதிவு', 'color': 'warning'},
    'accepted': {'name': 'Order Accepted', 'name_tamil': 'ஆர்டர் ஏற்றுக்கொள்ளப்பட்டது', 'color': 'info'},
    'packing': {'name': 'Packing', 'name_tamil': 'பொட்டலம் செய்யப்படுகிறது', 'color': 'primary'},
    'packed': {'name': 'Packed', 'name_tamil': 'பொட்டலம் முடிந்தது', 'color': 'secondary'},
    'shipped': {'name': 'Shipped', 'name_tamil': 'அனுப்பப்பட்டது', 'color': 'info'},
    'delivered': {'name': 'Delivered', 'name_tamil': 'பெறப்பட்டது', 'color': 'success'},
    'cancelled': {'name': 'Cancelled', 'name_tamil': 'ரத்து செய்யப்பட்டது', 'color': 'danger'}
}

# Payment status
PAYMENT_STATUS = {
    'pending': {'name': 'Payment Pending', 'name_tamil': 'பணம் செலுத்த வேண்டும்', 'color': 'warning'},
    'paid': {'name': 'Payment Received', 'name_tamil': 'பணம் பெறப்பட்டது', 'color': 'success'},
    'failed': {'name': 'Payment Failed', 'name_tamil': 'பணம் செலுத்தல் தோல்வி', 'color': 'danger'}
}

# User roles
USER_ROLES = {
    'customer': {'name': 'Customer', 'permissions': ['view_products', 'place_orders']},
    'storekeeper': {'name': 'Store Keeper', 'permissions': ['manage_orders', 'update_inventory']},
    'admin': {'name': 'Administrator', 'permissions': ['all']}
}

# Weight options for products (in kg)
WEIGHT_OPTIONS = [0.25, 0.5, 1, 2, 3, 5, 10]

# GST rates
GST_RATES = [0, 5, 12, 18, 28]

# Default product images by category
DEFAULT_IMAGES = {
    'vegetables': '/static/images/default-vegetable.svg',
    'fruits': '/static/images/default-fruit.svg',
    'grains': '/static/images/default-grain.svg',
    'spices': '/static/images/default-spice.svg',
    'dairy': '/static/images/default-dairy.svg',
    'oils': '/static/images/default-oil.svg'
}

# Email templates
EMAIL_TEMPLATES = {
    'order_confirmation': {
        'subject': 'Order Confirmation - {order_number}',
        'subject_tamil': 'ஆர்டர் உறுதிப்படுத்தல் - {order_number}'
    },
    'order_status_update': {
        'subject': 'Order Status Update - {order_number}',
        'subject_tamil': 'ஆர்டர் நிலை புதுப்பிப்பு - {order_number}'
    }
}

# WhatsApp message templates
WHATSAPP_TEMPLATES = {
    'order_confirmation': {
        'message': 'Hi {customer_name}, your order {order_number} has been confirmed. Total: ₹{total_amount}. Thank you for choosing Thaavaram!',
        'message_tamil': 'வணக்கம் {customer_name}, உங்கள் ஆர்டர் {order_number} உறுதிப்படுத்தப்பட்டது. மொத்தம்: ₹{total_amount}. தாவரத்தை தேர்ந்தெடுத்ததற்கு நன்றி!'
    },
    'order_shipped': {
        'message': 'Your order {order_number} has been shipped! Track: {tracking_url}',
        'message_tamil': 'உங்கள் ஆர்டர் {order_number} அனுப்பப்பட்டது! கண்காணிக்க: {tracking_url}'
    }
}

# Delivery partners
DELIVERY_PARTNERS = {
    'delhivery': {'name': 'Delhivery', 'tracking_url': 'https://www.delhivery.com/track/package/'},
    'bluedart': {'name': 'Blue Dart', 'tracking_url': 'https://www.bluedart.com/tracking/'},
    'dtdc': {'name': 'DTDC', 'tracking_url': 'https://www.dtdc.in/tracking/'},
    'local': {'name': 'Local Delivery', 'tracking_url': ''}
}
