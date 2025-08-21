#!/usr/bin/env python3

import requests

session = requests.Session()
base_url = "https://9a77f1e9-1cf0-4dfc-b14d-03c2a93ef81c-00-1369746tok8bu.janeway.replit.dev"

# Step 1: Login
print("1. Logging in...")
login_data = {'email': 'admin@thaavaram.com', 'password': '123'}
login_resp = session.post(f"{base_url}/login", data=login_data)
print(f"Login status: {login_resp.status_code}")

# Step 2: Access admin dashboard  
print("2. Accessing admin dashboard...")
admin_resp = session.get(f"{base_url}/admin")
print(f"Admin dashboard status: {admin_resp.status_code}")
if admin_resp.status_code == 200:
    print("✅ Admin dashboard accessible")

# Step 3: Access homepage settings
print("3. Accessing homepage settings...")
settings_resp = session.get(f"{base_url}/admin/homepage-settings")
print(f"Homepage settings status: {settings_resp.status_code}")

if settings_resp.status_code == 200:
    print("✅ Homepage settings accessible")
    
    # Check for invoice logo fields
    content = settings_resp.text
    if "Invoice Logo Settings" in content:
        print("✅ Invoice Logo Settings section found")
    else:
        print("❌ Invoice Logo Settings section NOT found")
        
    if "invoice_logo_url" in content:
        print("✅ Invoice logo URL field found")
    else:
        print("❌ Invoice logo URL field NOT found")
        
    if "invoice_upi_logo_url" in content:
        print("✅ UPI logo URL field found")
    else:
        print("❌ UPI logo URL field NOT found")
        
    # Show what sections ARE present
    print("\n=== SECTIONS FOUND ===")
    if "Store Information" in content:
        print("✅ Store Information")
    if "Payment Settings" in content:
        print("✅ Payment Settings")
    if "Contact Information" in content:
        print("✅ Contact Information")
    if "Delivery Settings" in content:
        print("✅ Delivery Settings")
        
else:
    print("❌ Cannot access homepage settings")
    print("Response:", settings_resp.text[:200])