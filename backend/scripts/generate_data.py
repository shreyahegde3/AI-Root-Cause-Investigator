import os
import sys
import random
from datetime import date, timedelta
from sqlalchemy import insert
from sqlalchemy.orm import Session as SqlalchemySession

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import engine, SessionLocal, Base
from app.models.models import Customer, Product, Order, Session as DbSession

# Settings
NUM_CUSTOMERS = 5000
NUM_PRODUCTS = 500
TARGET_ORDERS = 100000
START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 4, 30)

# Categories and product templates
CATEGORIES = {
    'Electronics': [
        'SmartPhone', 'Laptop', 'Wireless Earbuds', 'Bluetooth Speaker', 
        'Smart Watch', 'Tablet', 'Gaming Console', '4K Monitor', 'Keyboard Wireless'
    ],
    'Apparel': [
        'Slim Fit Jeans', 'Running Shoes', 'Cotton T-Shirt', 'Summer Dress', 'Leather Belt',
        'Denim Jacket', 'Sneakers Classic', 'Woolen Sweater', 'Socks Pack', 'Baseball Cap'
    ],
    'Home & Kitchen': [
        'Air Fryer', 'Coffee Maker', 'Stainless Steel Pan', 'Vacuum Cleaner', 'Bed Sheets',
        'Blender Max', 'Microwave Oven', 'Knife Set', 'Water Filter', 'Robot Vacuum'
    ],
    'Office Supplies': [
        'Ergonomic Chair', 'Gel Pens Pack', 'Wireless Mouse', 'Notebook Standard', 'Desk Organizer',
        'Whiteboard Large', 'Stapler Heavy Duty', 'Printer Paper Case', 'Standing Desk Converter'
    ],
    'Beauty': [
        'Face Wash', 'Moisturizing Cream', 'Shampoo', 'Fragrance Classic', 'Lipstick Red',
        'Sunscreen SPF 50', 'Hair Dryer', 'Face Serum', 'Eye Cream', 'Body Lotion'
    ]
}

PREFIXES = ["Premium", "Pro", "Eco", "Elite", "Basic", "Ultra", "Deluxe", "Classic", "Smart", "Signature"]
SEGMENTS = ['Consumer', 'Corporate', 'Home Office']

CITIES = {
    'South': [
        ('Bangalore', 'Karnataka'),
        ('Chennai', 'Tamil Nadu'),
        ('Hyderabad', 'Telangana'),
        ('Kochi', 'Kerala'),
        ('Coimbatore', 'Tamil Nadu')
    ],
    'North': [
        ('Delhi', 'Delhi'),
        ('Noida', 'Uttar Pradesh'),
        ('Gurgaon', 'Haryana'),
        ('Chandigarh', 'Punjab'),
        ('Lucknow', 'Uttar Pradesh'),
        ('Jaipur', 'Rajasthan')
    ],
    'West': [
        ('Mumbai', 'Maharashtra'),
        ('Pune', 'Maharashtra'),
        ('Ahmedabad', 'Gujarat'),
        ('Surat', 'Gujarat'),
        ('Nagpur', 'Maharashtra')
    ],
    'East': [
        ('Kolkata', 'West Bengal'),
        ('Patna', 'Bihar'),
        ('Bhubaneswar', 'Odisha'),
        ('Guwahati', 'Assam'),
        ('Ranchi', 'Jharkhand')
    ]
}

def generate_customers():
    print(f"Generating {NUM_CUSTOMERS} customers...")
    customers = []
    for i in range(1, NUM_CUSTOMERS + 1):
        cust_id = f"C{i:05d}"
        segment = random.choice(SEGMENTS)
        region = random.choice(list(CITIES.keys()))
        city, state = random.choice(CITIES[region])
        customers.append({
            'customer_id': cust_id,
            'segment': segment,
            'city': city,
            'state': state
        })
    return customers

def generate_products():
    print(f"Generating {NUM_PRODUCTS} products...")
    products = []
    product_price_map = {}
    categories_list = list(CATEGORIES.keys())
    
    for i in range(1, NUM_PRODUCTS + 1):
        prod_id = f"P{i:05d}"
        category = random.choice(categories_list)
        base_item = random.choice(CATEGORIES[category])
        prefix = random.choice(PREFIXES)
        name = f"{prefix} {base_item} {random.randint(100, 999)}"
        
        # Base price by category
        if category == 'Electronics':
            price = round(random.uniform(150.0, 1200.0), 2)
        elif category == 'Apparel':
            price = round(random.uniform(15.0, 100.0), 2)
        elif category == 'Home & Kitchen':
            price = round(random.uniform(25.0, 400.0), 2)
        elif category == 'Office Supplies':
            price = round(random.uniform(5.0, 250.0), 2)
        else:  # Beauty
            price = round(random.uniform(10.0, 80.0), 2)
            
        products.append({
            'product_id': prod_id,
            'category': category,
            'product_name': name
        })
        product_price_map[prod_id] = (price, category)
        
    return products, product_price_map

def generate_orders_and_sessions(customers, products, product_price_map):
    print("Generating orders and sessions...")
    orders = []
    sessions = []
    
    total_days = (END_DATE - START_DATE).days + 1
    
    # Pre-split customers by region and segment for faster access
    customers_by_region_segment = {}
    for r in CITIES.keys():
        for s in SEGMENTS:
            customers_by_region_segment[(r, s)] = []
            
    for c in customers:
        # Find region
        region = next(r for r, cities in CITIES.items() if any(item[0] == c['city'] for item in cities))
        customers_by_region_segment[(region, c['segment'])].append(c)

    # Split products by category
    products_by_category = {}
    for p in products:
        cat = p['category']
        if cat not in products_by_category:
            products_by_category[cat] = []
        products_by_category[cat].append(p)

    all_product_ids = list(product_price_map.keys())
    
    # Target average orders per day to hit ~100k total
    # (accounting for February drop and other rejections, target slightly higher base)
    base_orders_per_day = 230
    order_id_counter = 1
    session_id_counter = 1

    current_date = START_DATE
    
    while current_date <= END_DATE:
        day_idx = (current_date - START_DATE).days
        day_of_week = current_date.weekday() # 0 = Monday, 6 = Sunday
        
        # 1. Seasonality Factors
        # Weekday vs Weekend (Weekdays have ~40% more traffic/orders)
        dow_factor = 1.2 if day_of_week < 5 else 0.7
        # Month factors (Nov-Dec holiday shopping, Jan recovery, April tax/spring)
        month = current_date.month
        month_factor = 1.0
        if month in [11, 12]:
            month_factor = 1.4
        elif month == 1:
            month_factor = 0.95
        
        # Upward organic growth trend (~12% growth over 16 months)
        growth_factor = 1.0 + (day_idx / total_days) * 0.12
        
        # Calculate base orders for this day
        daily_mean_orders = base_orders_per_day * dow_factor * month_factor * growth_factor
        
        # 2. Check for February 2026 conversion rate drop anomaly (overall order drop)
        is_feb_2026_anomaly = (current_date.year == 2026 and current_date.month == 2)
        if is_feb_2026_anomaly:
            # 35% orders drop across the board
            daily_mean_orders *= 0.65

        # Determine actual orders count for this day
        daily_orders_count = int(random.normalvariate(daily_mean_orders, daily_mean_orders ** 0.5))
        daily_orders_count = max(50, daily_orders_count) # Ensure at least some orders
        
        # Regional and Segment shares
        regional_shares = {'South': 0.35, 'North': 0.25, 'West': 0.25, 'East': 0.15}
        segment_shares = {'Consumer': 0.5, 'Corporate': 0.3, 'Home Office': 0.2}

        # Generate orders for the day
        day_orders_count_actual = 0
        for _ in range(daily_orders_count):
            # Select region and segment based on distribution
            region = random.choices(list(regional_shares.keys()), list(regional_shares.values()))[0]
            segment = random.choices(list(segment_shares.keys()), list(segment_shares.values()))[0]
            
            cust_list = customers_by_region_segment[(region, segment)]
            if not cust_list:
                continue
            customer = random.choice(cust_list)
            
            # Select product
            prod_id = random.choice(all_product_ids)
            price, category = product_price_map[prod_id]
            
            # 3. Check for specific anomalies to reject orders
            
            # Anomaly A: Bangalore Electronics drop in second half of April 2026
            # Orders drop by 85% for Electronics in Bangalore
            is_bangalore_electronics_anomaly = (
                current_date.year == 2026 
                and current_date.month == 4 
                and current_date.day >= 15
                and customer['city'] == 'Bangalore'
                and category == 'Electronics'
            )
            if is_bangalore_electronics_anomaly:
                if random.random() < 0.85:
                    continue # Reject/drop order

            # Anomaly B: Office Supplies drop in Corporate segment during October 2025
            # Orders drop by 75%
            is_corp_office_supplies_anomaly = (
                current_date.year == 2025
                and current_date.month == 10
                and customer['segment'] == 'Corporate'
                and category == 'Office Supplies'
            )
            if is_corp_office_supplies_anomaly:
                if random.random() < 0.75:
                    continue # Reject/drop order
            
            quantity = random.choices([1, 2, 3, 4, 5], [0.6, 0.25, 0.1, 0.03, 0.02])[0]
            
            orders.append({
                'order_id': f"O{order_id_counter:08d}",
                'customer_id': customer['customer_id'],
                'product_id': prod_id,
                'region': region,
                'category': category,
                'price': price,
                'quantity': quantity,
                'order_date': current_date
            })
            order_id_counter += 1
            day_orders_count_actual += 1

        # 4. Generate daily sessions for this day (by region and segment)
        # Session counts should NOT drop during anomalies to represent drop in conversion
        for region in regional_shares.keys():
            for segment in segment_shares.keys():
                # Normal orders expectation (without February drop or other anomalies)
                norm_daily_mean = base_orders_per_day * dow_factor * month_factor * growth_factor
                expected_combo_orders = norm_daily_mean * regional_shares[region] * segment_shares[segment]
                
                # Conversion rate base = 2.5%
                base_conversion_rate = 0.025
                # Normal sessions needed to support this
                normal_sessions = int(expected_combo_orders / base_conversion_rate)
                # Add some random daily fluctuation
                sessions_count = int(normal_sessions * random.uniform(0.9, 1.1))
                sessions_count = max(100, sessions_count)

                sessions.append({
                    'session_id': f"S{session_id_counter:08d}",
                    'session_date': current_date,
                    'region': region,
                    'segment': segment,
                    'sessions_count': sessions_count
                })
                session_id_counter += 1
                
        current_date += timedelta(days=1)
        
    print(f"Generated {len(orders)} orders and {len(sessions)} session records.")
    return orders, sessions

def main():
    print("Database data initialization starting...")
    
    # 1. Establish connection and create tables
    try:
        print("Recreating database tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error connecting to database or creating tables: {e}")
        sys.exit(1)
        
    # 2. Generate records
    customers = generate_customers()
    products, product_price_map = generate_products()
    orders, sessions = generate_orders_and_sessions(customers, products, product_price_map)
    
    # 3. Load records into PostgreSQL
    db = SessionLocal()
    try:
        # Load customers
        print("Loading customers into DB...")
        db.execute(insert(Customer), customers)
        db.commit()
        
        # Load products
        print("Loading products into DB...")
        db.execute(insert(Product), products)
        db.commit()
        
        # Load orders in chunks for safety
        print("Loading orders into DB...")
        chunk_size = 10000
        for i in range(0, len(orders), chunk_size):
            chunk = orders[i:i+chunk_size]
            db.execute(insert(Order), chunk)
            db.commit()
            print(f"Loaded orders {i} to {min(i+chunk_size, len(orders))}")
            
        # Load sessions in chunks
        print("Loading sessions into DB...")
        for i in range(0, len(sessions), chunk_size):
            chunk = sessions[i:i+chunk_size]
            db.execute(insert(DbSession), chunk)
            db.commit()
            print(f"Loaded sessions {i} to {min(i+chunk_size, len(sessions))}")
            
        print("All data generated and loaded successfully!")
        
    except Exception as e:
        print(f"Error loading data: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == '__main__':
    main()
