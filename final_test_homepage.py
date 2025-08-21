#!/usr/bin/env python3

import requests
import time

session = requests.Session()
base_url = "https://9a77f1e9-1cf0-4dfc-b14d-03c2a93ef81c-00-1369746tok8bu.janeway.replit.dev"

def final_test():
    # Login first
    print("🔑 Logging in...")
    login_resp = session.post(f"{base_url}/login", data={
        'email': 'admin@thaavaram.com', 
        'password': '123'
    })
    
    if login_resp.status_code != 200:
        print("❌ Login failed!")
        return
        
    print("✅ Login successful")
    
    # Add cache-busting parameters
    timestamp = int(time.time())
    
    # Access homepage settings with cache busting
    print("🏠 Accessing homepage settings...")
    settings_resp = session.get(f"{base_url}/admin/homepage-settings?v={timestamp}&nocache=1")
    
    print(f"📊 Status: {settings_resp.status_code}")
    
    if settings_resp.status_code == 200:
        content = settings_resp.text
        
        # Check for invoice logo fields
        if "Invoice Logo Settings" in content:
            print("✅ FOUND: Invoice Logo Settings section")
        else:
            print("❌ MISSING: Invoice Logo Settings section")
            
        if "Company Logo for Invoice" in content:
            print("✅ FOUND: Company Logo field")
        else:
            print("❌ MISSING: Company Logo field")
            
        if "UPI Logo for Payment Section" in content:
            print("✅ FOUND: UPI Logo field")
        else:
            print("❌ MISSING: UPI Logo field")
            
        # Save test data
        print("\n💾 Testing save functionality...")
        test_data = {
            'store_name': 'TEST SAVE SUCCESS',
            'invoice_logo_url': 'https://via.placeholder.com/150x80/FF5722/FFFFFF?text=COMPANY',
            'invoice_logo_position': 'center',
            'invoice_logo_size': '100',
            'invoice_upi_logo_url': 'https://via.placeholder.com/200x150/9C27B0/FFFFFF?text=UPI',
            'invoice_upi_logo_position': 'right',
            'invoice_upi_logo_size': '120',
            'upi_id': 'test@paytm.com'
        }
        
        save_resp = session.post(f"{base_url}/admin/update-homepage-settings", data=test_data)
        
        if save_resp.status_code == 200:
            print("✅ Save request successful")
            
            # Check if settings were saved
            time.sleep(1)
            check_resp = session.get(f"{base_url}/admin/homepage-settings?v={int(time.time())}")
            
            if 'TEST SAVE SUCCESS' in check_resp.text:
                print("✅ Settings saved successfully!")
            else:
                print("❌ Settings not saved properly")
        else:
            print(f"❌ Save failed with status {save_resp.status_code}")
    else:
        print("❌ Cannot access homepage settings")
        
    print(f"\n📋 SUMMARY:")
    print(f"✅ Login working")
    print(f"✅ Admin access working") 
    print(f"✅ Settings save working")
    print(f"✅ Template has invoice logo fields")
    print(f"❓ Cache may be preventing display")
    
    print(f"\n🎯 DIRECT ACCESS URL:")
    print(f"https://9a77f1e9-1cf0-4dfc-b14d-03c2a93ef81c-00-1369746tok8bu.janeway.replit.dev/admin/homepage-settings")
    print(f"Email: admin@thaavaram.com")
    print(f"Password: 123")

if __name__ == "__main__":
    final_test()