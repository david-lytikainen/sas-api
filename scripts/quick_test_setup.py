#!/usr/bin/env python3
"""
Quick test setup script for SAS API development.
Creates test data with various configurations for easy development testing.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from create_test_data import main as create_main
import argparse

def quick_free_event():
    """Quickly create a free event with test users"""
    print("🆓 Creating FREE event with test users...")
    sys.argv = ['quick_test_setup.py', '--event-type', 'free']
    create_main()

def quick_paid_event():
    """Quickly create a paid event with test users (payment bypassed)"""
    print("💰 Creating PAID event with test users (payment bypassed)...")
    sys.argv = ['quick_test_setup.py', '--event-type', 'paid']
    create_main()

def quick_both_events():
    """Quickly create both free and paid events with test users"""
    print("🎯 Creating BOTH free and paid events with test users...")
    sys.argv = ['quick_test_setup.py', '--event-type', 'both']
    create_main()

def quick_paid_with_real_payment():
    """Create a paid event that requires real payment (for testing payment flow)"""
    print("💳 Creating PAID event with REAL payment requirements...")
    sys.argv = ['quick_test_setup.py', '--event-type', 'paid', '--no-payment-bypass']
    create_main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Quick test setup for SAS API')
    parser.add_argument('setup_type', 
                       choices=['free', 'paid', 'both', 'paid-real'], 
                       nargs='?', 
                       default='both',
                       help='Quick setup type (default: both)')
    
    args = parser.parse_args()
    
    if args.setup_type == 'free':
        quick_free_event()
    elif args.setup_type == 'paid':
        quick_paid_event()
    elif args.setup_type == 'both':
        quick_both_events()
    elif args.setup_type == 'paid-real':
        quick_paid_with_real_payment()
    
    print("\n🎉 Quick setup complete!")
    print("💡 You can now test with the following users:")
    print("   - Admin: admin@example.com / admin123")
    print("   - Test users: male1@test.com / test123, female1@test.com / test123, etc.") 