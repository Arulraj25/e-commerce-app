from flask import Flask, jsonify, request
from flask_cors import CORS
import pymysql
import os
import time
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Database configuration
def get_db_config():
    return {
        'host': os.getenv('MYSQL_HOST', 'mysql'),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', 'simple123'),
        'database': os.getenv('MYSQL_DATABASE', 'e_commerce_db'),
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }

def get_db_connection():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return pymysql.connect(**get_db_config())
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection failed, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(5)
            else:
                raise e

# Initialize database tables
def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Create products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL,
                    image_url VARCHAR(500),
                    category VARCHAR(100),
                    stock_quantity INT DEFAULT 10,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create orders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_name VARCHAR(255) NOT NULL,
                    customer_email VARCHAR(255) NOT NULL,
                    customer_phone VARCHAR(20),
                    customer_address TEXT NOT NULL,
                    total_amount DECIMAL(10, 2) NOT NULL,
                    items JSON NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert sample products if empty
            cursor.execute("SELECT COUNT(*) as count FROM products")
            if cursor.fetchone()['count'] == 0:
                sample_products = [
                    ('MacBook Pro', 'Powerful laptop for professionals', 1999.99, 'https://images.unsplash.com/photo-1511385348-a52b4a160dc2?w=400', 'Electronics', 15),
                    ('iPhone 15', 'Latest smartphone with advanced features', 999.99, 'https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=400', 'Electronics', 25),
                    ('Sony Headphones', 'Wireless noise-canceling headphones', 299.99, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400', 'Electronics', 30),
                    ('Cotton T-Shirt', 'Comfortable cotton t-shirt', 24.99, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400', 'Clothing', 50)
                ]
                
                cursor.executemany('''
                    INSERT INTO products (name, description, price, image_url, category, stock_quantity)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', sample_products)
            
            conn.commit()
            print("✅ Database initialized successfully!")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Routes
@app.route('/')
def hello():
    return jsonify({
        "message": "E-Commerce Backend API is running!",
        "endpoints": {
            "GET /health": "Health check",
            "GET /products": "Get all products",
            "POST /products": "Add new product",
            "POST /orders": "Create new order",
            "GET /orders": "Get all orders"
        }
    })

@app.route('/health')
def health_check():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# Product endpoints
@app.route('/products')
def get_products():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM products ORDER BY created_at DESC")
            products = cursor.fetchall()
        conn.close()
        return jsonify(products)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/products', methods=['POST'])
def add_product():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('price'):
            return jsonify({"error": "Name and price are required"}), 400
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO products (name, price, description, image_url, category, stock_quantity) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                data['name'],
                float(data['price']),
                data.get('description', ''),
                data.get('image_url'),
                data.get('category', 'General'),
                data.get('stock_quantity', 10)
            ))
        
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            "message": "Product added successfully",
            "product_id": product_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Order endpoints - FIXED VERSION
@app.route('/orders', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        print("📦 Received order data:", data)  # Debug log
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Validate required fields
        required_fields = ['customer_name', 'customer_email', 'customer_address', 'total_amount', 'items']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        if not isinstance(data['items'], list) or len(data['items']) == 0:
            return jsonify({"error": "Items must be a non-empty list"}), 400
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO orders (customer_name, customer_email, customer_phone, customer_address, total_amount, items, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                data['customer_name'],
                data['customer_email'],
                data.get('customer_phone', ''),
                data['customer_address'],
                float(data['total_amount']),
                json.dumps(data['items']),
                'pending'
            ))
            
            order_id = cursor.lastrowid
            conn.commit()
        
        conn.close()
        
        return jsonify({
            "order_id": order_id, 
            "message": "Order created successfully",
            "status": "pending"
        })
        
    except Exception as e:
        print(f"❌ Order creation error: {e}")  # Debug log
        return jsonify({"error": str(e)}), 500

@app.route('/orders')
def get_orders():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *, 
                       DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as order_date 
                FROM orders 
                ORDER BY created_at DESC
            """)
            orders = cursor.fetchall()
            
            # Parse JSON items
            for order in orders:
                if isinstance(order['items'], str):
                    order['items'] = json.loads(order['items'])
                    
        conn.close()
        return jsonify(orders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting E-Commerce Backend...")
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
