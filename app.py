from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from geopy.distance import geodesic
from sqlalchemy import or_
from train.predict import predict
from dataclasses import dataclass
import json
from flask_migrate import Migrate
import csv # Import the csv module

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///food_platform.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
import_food_data = 1 # Set to 1 to import food data, 0 to skip

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_store = db.Column(db.Boolean, default=False)
    gender = db.Column(db.String(1))  # 'M' or 'F'
    birthdate = db.Column(db.Date)

    def get_age(self):
        if self.birthdate:
            today = datetime.today()
            return today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
        return None

@dataclass
class NutritionNeeds:
    calories: float  # kcal
    protein: float  # g
    fat: float  # g
    carbs: float  # g
    fiber: float  # g
    sodium: float  # mg

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    quantity = db.Column(db.Integer, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    expiry_date = db.Column(db.DateTime, nullable=False)
    original_price = db.Column(db.Float, nullable=False)
    discount_rate = db.Column(db.Float, nullable=False)
    nutrition_info = db.Column(db.JSON)
    store_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    store = db.relationship('User', backref=db.backref('products', lazy=True))
    cart_count = db.Column(db.Integer, default=0)  # 新增：追蹤購物車數量

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'quantity': self.quantity,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d'),
            'original_price': self.original_price,
            'discount_rate': self.discount_rate,
            'discounted_price': self.original_price * self.discount_rate,
            'nutrition_info': self.nutrition_info,
            'store_id': self.store_id,
            'store_username': self.store.username,
            'cart_count': self.cart_count  # 新增：返回購物車數量
        }

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
    product = db.relationship('Product', backref=db.backref('cart_items', lazy=True))

def calculate_nutrition_needs(user: User) -> NutritionNeeds:
    age = user.get_age()
    gender = user.gender

    if not age or not gender:
        # Default values if age or gender not set
        return NutritionNeeds(
            calories=2000,
            protein=65,
            fat=55,
            carbs=300,
            fiber=25,
            sodium=2000
        )

    # Based on Taiwan dietary reference intakes
    if gender == 'M':
        if 19 <= age <= 30:
            return NutritionNeeds(
                calories=2700,
                protein=65,
                fat=60,  # 20-30% of calories
                carbs=394,  # 55-65% of calories
                fiber=25,
                sodium=2000
            )
        elif 31 <= age <= 50:
            return NutritionNeeds(
                calories=2500,
                protein=65,
                fat=56,
                carbs=365,
                fiber=25,
                sodium=2000
            )
        elif 51 <= age <= 70:
            return NutritionNeeds(
                calories=2200,
                protein=65,
                fat=49,
                carbs=321,
                fiber=25,
                sodium=2000
            )
        else:  # > 70
            return NutritionNeeds(
                calories=2000,
                protein=65,
                fat=44,
                carbs=292,
                fiber=25,
                sodium=2000
            )
    else:  # gender == 'F'
        if 19 <= age <= 30:
            return NutritionNeeds(
                calories=2100,
                protein=50,
                fat=47,
                carbs=306,
                fiber=25,
                sodium=2000
            )
        elif 31 <= age <= 50:
            return NutritionNeeds(
                calories=2000,
                protein=50,
                fat=44,
                carbs=292,
                fiber=25,
                sodium=2000
            )
        elif 51 <= age <= 70:
            return NutritionNeeds(
                calories=1800,
                protein=50,
                fat=40,
                carbs=263,
                fiber=25,
                sodium=2000
            )
        else:  # > 70
            return NutritionNeeds(
                calories=1600,
                protein=50,
                fat=36,
                carbs=233,
                fiber=25,
                sodium=2000
            )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    # 獲取搜尋參數
    search = request.args.get('search', '').strip()
    max_price = request.args.get('max_price', type=float)
    distance = request.args.get('distance', type=float)
    user_lat = request.args.get('user_lat', type=float)
    user_lon = request.args.get('user_lon', type=float)

    # 基本查詢
    query = Product.query

    # 關鍵字搜尋（商品名稱或地址）
    if search:
        query = query.filter(or_(
            Product.name.ilike(f'%{search}%'),
            Product.address.ilike(f'%{search}%')
        ))

    # 價格篩選（考慮折扣後的價格）
    if max_price is not None and max_price > 0:
        query = query.filter(Product.original_price * Product.discount_rate <= max_price)

    # 執行查詢
    products = query.all()

    # 如果有設定距離篩選且有用戶位置，進行距離篩選
    if distance is not None and distance > 0 and user_lat is not None and user_lon is not None:
        filtered_products = []
        user_location = (user_lat, user_lon)
        
        for product in products:
            # 初始化距離為 None
            product.distance = None
            
            # 只有當商品有完整的經緯度資訊時才計算距離
            if product.latitude is not None and product.longitude is not None:
                try:
                    product_location = (product.latitude, product.longitude)
                    # 計算距離（公里）
                    dist = geodesic(user_location, product_location).kilometers
                    product.distance = round(dist, 2)
                    
                    # 只添加在指定距離範圍內的商品
                    if dist <= distance:
                        filtered_products.append(product)
                except ValueError:
                    # 如果計算距離時發生錯誤，將商品距離設為 None
                    product.distance = None
            else:
                filtered_products.append(product)
            
        products = filtered_products
    else:
        # 如果沒有進行距離篩選，確保所有商品的距離屬性都被設置為 None
        for product in products:
            product.distance = None

    return render_template('index.html', 
                         products=products,
                         search=search,
                         max_price=max_price,
                         distance=distance,
                         user_lat=user_lat,
                         user_lon=user_lon)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_store = request.form.get('is_store') == 'on'
        gender = request.form.get('gender')
        birthdate = request.form.get('birthdate')

        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('此使用者名稱已被使用', 'error')
            return render_template('register.html')

        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('此電子郵件已被註冊', 'error')
            return render_template('register.html')

        try:
            birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date() if birthdate else None
        except ValueError:
            flash('生日格式不正確', 'error')
            return render_template('register.html')

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_store=is_store,
            gender=gender,
            birthdate=birthdate
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash('註冊成功！請登入', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('註冊時發生錯誤，請稍後再試', 'error')
            return render_template('register.html')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def get_coordinates(address):
    try:
        geolocator = Nominatim(user_agent="my_food_platform")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        return None, None
    except GeocoderTimedOut:
        return None, None

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/product/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # 確認是否為商品所屬店家
    if current_user.id != product.store_id:
        flash('您沒有權限編輯此商品')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # 獲取新的數量
    new_quantity = request.form.get('quantity', type=int)
    if new_quantity is not None and new_quantity >= 0:
        product.quantity = new_quantity
        db.session.commit()
        flash('商品數量已更新')
    else:
        flash('無效的數量')
    
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # 確認是否為商品所屬店家
    if current_user.id != product.store_id:
        flash('您沒有權限刪除此商品')
        return redirect(url_for('product_detail', product_id=product_id))
    
    db.session.delete(product)
    db.session.commit()
    flash('商品已下架')
    
    return redirect(url_for('index'))

@app.route('/check_coordinates')
def check_coordinates():
    address = request.args.get('address')
    if not address:
        return jsonify({'success': False, 'error': 'No address provided'})
    
    try:
        lat, lon = get_coordinates(address)
        if lat is not None and lon is not None:
            return jsonify({
                'success': True,
                'latitude': lat,
                'longitude': lon
            })
        return jsonify({'success': False, 'error': 'Could not geocode address'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/predict_nutrition', methods=['POST'])
def predict_nutrition():
    try:
        data = request.get_json()
        food_name = data.get('food_name')
        
        if not food_name:
            return jsonify({'success': False, 'error': '請提供食物名稱'})

        # 使用 predict.py 中的預測函數
        nutrition_values = predict(food_name)
        
        # 轉換預測結果格式以符合前端期望，並四捨五入到小數點後兩位
        formatted_values = {
            'energy': round(nutrition_values['Energy']['value'], 2),
            'protein': round(nutrition_values['Protein']['value'], 2),
            'fat': round(nutrition_values['Fat']['value'], 2),
            'carbohydrate': round(nutrition_values['Carbohydrate']['value'], 2),
            'fiber': round(nutrition_values['Fiber']['value'], 2),
            'sugars': round(nutrition_values['Sugars']['value'], 2),
            'sodium': round(nutrition_values['Sodium']['value'], 2)
        }

        return jsonify({
            'success': True,
            'nutrition': formatted_values
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_store:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        address = request.form.get('address')
        
        # 嘗試從表單獲取手動輸入的經緯度
        manual_lat = request.form.get('latitude')
        manual_lon = request.form.get('longitude')
        
        # 如果有手動輸入的經緯度，使用手動輸入的值
        if manual_lat and manual_lon:
            lat = float(manual_lat)
            lon = float(manual_lon)
        else:
            # 否則嘗試自動獲取經緯度
            lat, lon = get_coordinates(address)
        
        # 收集營養成分數據並四捨五入到小數點後兩位
        nutrition_info = {
            'energy': round(float(request.form.get('energy', 0)), 2),
            'protein': round(float(request.form.get('protein', 0)), 2),
            'fat': round(float(request.form.get('fat', 0)), 2),
            'carbohydrate': round(float(request.form.get('carbohydrate', 0)), 2),
            'fiber': round(float(request.form.get('fiber', 0)), 2),
            'sugars': round(float(request.form.get('sugars', 0)), 2),
            'sodium': round(float(request.form.get('sodium', 0)), 2)
        }
        
        product = Product(
            name=request.form.get('name'),
            description=request.form.get('description'),
            quantity=int(request.form.get('quantity')),
            address=address,
            latitude=lat,
            longitude=lon,
            expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d'),
            original_price=float(request.form.get('original_price')),
            discount_rate=float(request.form.get('discount_rate', 0.5)),
            nutrition_info=nutrition_info,
            store_id=current_user.id
        )
        
        # 如果無法獲取經緯度，添加提示訊息
        if lat is None or lon is None:
            flash('無法自動獲取地址的經緯度，商品位置將無法在地圖上顯示', 'warning')
            
        db.session.add(product)
        db.session.commit()

        # Update info_food.csv with the new product's nutrition data
        csv_file_path = 'info_food.csv'
        headers = [
            "food_name", "energy", "protein", "total_lipid_fat",
            "carbohydrate_by_difference", "fiber_total_dietary",
            "total_sugars", "sodium_na"
        ]
        
        # Check if the file exists and is empty to write headers
        file_exists = os.path.exists(csv_file_path)
        write_headers = not file_exists or os.stat(csv_file_path).st_size == 0

        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if write_headers:
                writer.writerow(headers)
            
            # Prepare data to write
            nutrition_data = product.nutrition_info
            row = [
                product.name,
                round(nutrition_data.get('energy', 0), 2),
                round(nutrition_data.get('protein', 0), 2),
                round(nutrition_data.get('fat', 0), 2), # maps to total_lipid_fat
                round(nutrition_data.get('carbohydrate', 0), 2), # maps to carbohydrate_by_difference
                round(nutrition_data.get('fiber', 0), 2), # maps to fiber_total_dietary
                round(nutrition_data.get('sugars', 0), 2), # maps to total_sugars
                round(nutrition_data.get('sodium', 0), 2) # maps to sodium_na
            ]
            writer.writerow(row)

        return redirect(url_for('index'))
        
    return render_template('add_product.html')

@app.route('/get_recommendations', methods=['POST'])
@login_required
def get_recommendations():
    if current_user.is_store:
        return jsonify({'error': 'Store accounts cannot use recommendations'}), 403

    data = request.get_json()
    user_lat = data.get('latitude')
    user_lon = data.get('longitude')
    max_price = data.get('max_price')

    # Get all available products
    products = Product.query.all()
    if not products:
        return jsonify({'error': 'No products available'}), 404

    # Calculate user's nutritional needs
    nutrition_needs = calculate_nutrition_needs(current_user)

    # Score and rank individual products
    scored_products = []
    for product in products:
        if not product.nutrition_info:
            continue

        # Calculate distance if location is available, otherwise set to 0
        if all([user_lat, user_lon, product.latitude, product.longitude]):
            distance = geodesic(
                (user_lat, user_lon),
                (product.latitude, product.longitude)
            ).kilometers
        else:
            distance = 0

        # Skip products beyond max price if specified
        discounted_price = product.original_price * product.discount_rate
        if max_price and discounted_price > max_price:
            continue

        # Calculate nutrition match score
        nutrition_score = 1 - (
            abs(float(product.nutrition_info.get('energy', 0)) / nutrition_needs.calories - 0.33) +
            abs(float(product.nutrition_info.get('protein', 0)) / nutrition_needs.protein - 0.33) +
            abs(float(product.nutrition_info.get('fat', 0)) / nutrition_needs.fat - 0.33) +
            abs(float(product.nutrition_info.get('carbohydrate', 0)) / nutrition_needs.carbs - 0.33) +
            abs(float(product.nutrition_info.get('fiber', 0)) / nutrition_needs.fiber - 0.33) +
            abs(float(product.nutrition_info.get('sodium', 0)) / nutrition_needs.sodium - 0.33)
        ) / 6  # 將差異值轉換為分數（差異越小，分數越高）

        # Calculate price score (lower price = higher score)
        max_price_score = max_price if max_price else max(p.original_price * p.discount_rate for p in products)
        price_score = 1 - (discounted_price / max_price_score)

        # Combined score (weighted average of nutrition and price, distance weight is 0 if no location)
        if distance == 0:
            total_score = (
                0.7 * nutrition_score +  # 增加營養評分的權重
                0.3 * price_score  # 增加價格權重
            )
        else:
            total_score = (
                0.5 * nutrition_score +
                0.25 * (1 / (1 + distance)) +
                0.25 * price_score
            )

        scored_products.append({
            'product': product.to_dict(),
            'distance': round(distance, 2),
            'score': total_score
        })

    # Sort by score and get top 3 individual products
    scored_products.sort(key=lambda x: x['score'], reverse=True)
    individual_recommendations = scored_products[:3]

    # Generate meal set recommendations
    meal_sets = []
    # Get top 10 products to create sets from
    top_products = scored_products[:10]
    
    from itertools import combinations
    possible_sets = list(combinations(top_products, 3))
    
    for product_set in possible_sets:
        # Calculate total nutrition for the set
        total_nutrition = {
            'energy': 0,
            'protein': 0,
            'fat': 0,
            'carbohydrate': 0,
            'fiber': 0,
            'sodium': 0
        }
        
        total_price = 0
        avg_distance = 0
        
        for item in product_set:
            product = item['product']
            nutrition = product['nutrition_info']
            
            for key in total_nutrition:
                total_nutrition[key] += float(nutrition.get(key, 0))
            
            total_price += product['original_price'] * product['discount_rate']
            avg_distance += item['distance']
        
        avg_distance /= len(product_set)
        
        # Calculate nutrition balance score for the set
        nutrition_balance = 1 - (
            abs(total_nutrition['energy'] / nutrition_needs.calories - 1.0) +
            abs(total_nutrition['protein'] / nutrition_needs.protein - 1.0) +
            abs(total_nutrition['fat'] / nutrition_needs.fat - 1.0) +
            abs(total_nutrition['carbohydrate'] / nutrition_needs.carbs - 1.0) +
            abs(total_nutrition['fiber'] / nutrition_needs.fiber - 1.0) +
            abs(total_nutrition['sodium'] / nutrition_needs.sodium - 1.0)
        ) / 6  # 將差異值轉換為分數（差異越小，分數越高）
        
        # Calculate price score
        price_score = 1 - (total_price / (max_price * 3 if max_price else max(p['product']['original_price'] * p['product']['discount_rate'] * 3 for p in scored_products)))
        
        # Calculate set score (adjust weights if no location data)
        if avg_distance == 0:
            set_score = (
                0.7 * nutrition_balance +  # 增加營養平衡的權重
                0.3 * price_score  # 增加價格權重
            )
        else:
            set_score = (
                0.5 * nutrition_balance +
                0.25 * (1 / (1 + avg_distance)) +
                0.25 * price_score
            )
        
        meal_sets.append({
            'products': [p['product'] for p in product_set],
            'total_nutrition': total_nutrition,
            'total_price': round(total_price, 2),
            'avg_distance': round(avg_distance, 2),
            'score': set_score
        })
    
    # Sort meal sets by score and get top 2
    meal_sets.sort(key=lambda x: x['score'], reverse=True)
    set_recommendations = meal_sets[:2]

    return jsonify({
        'individual_recommendations': individual_recommendations,
        'set_recommendations': set_recommendations,
        'nutrition_needs': {
            'calories': nutrition_needs.calories,
            'protein': nutrition_needs.protein,
            'fat': nutrition_needs.fat,
            'carbs': nutrition_needs.carbs,
            'fiber': nutrition_needs.fiber,
            'sodium': nutrition_needs.sodium
        }
    })

@app.route('/get_ai_recommendations', methods=['POST'])
@login_required
def get_ai_recommendations():
    if current_user.is_store:
        return jsonify({'success': False, 'error': '店家帳號無法使用AI建議'}), 403

    # Get user information for AI recommendation
    user_gender = current_user.gender if current_user.gender else 'male' # Default to male if not set
    user_age = current_user.get_age() if current_user.get_age() else 30 # Default to 30 if not set

    # Define the path to info_food.csv
    csv_file_path = 'info_food.csv'

    try:
        # Call the async get_recommendations function
        import asyncio
        from train.AI_food_recommendation import get_recommendations

        # Run the async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        recommendations = loop.run_until_complete(
            get_recommendations(csv_file_path, user_gender, user_age)
        )
        loop.close()

        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
    except Exception as e:
        print(f"Error getting AI recommendations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/cart')
@login_required
def view_cart():
    if current_user.is_store:
        return redirect(url_for('index'))
    
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.product.original_price * item.product.discount_rate * item.quantity 
                     for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/update_cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    if current_user.is_store:
        return jsonify({'success': False, 'message': '店家帳號無法修改購物車'}), 403
    
    data = request.get_json()
    change = data.get('change', 0)
    
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        return jsonify({'success': False, 'message': '無權限修改此購物車項目'}), 403
    
    new_quantity = cart_item.quantity + change
    if new_quantity < 1:
        return jsonify({'success': False, 'message': '商品數量不能小於1'}), 400
    
    cart_item.quantity = new_quantity
    try:
        db.session.commit()
        return jsonify({'success': True})
    except:
        db.session.rollback()
        return jsonify({'success': False, 'message': '更新失敗'}), 500

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    if current_user.is_store:
        return jsonify({'success': False, 'message': '店家帳號無法修改購物車'}), 403
    
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        return jsonify({'success': False, 'message': '無權限修改此購物車項目'}), 403
    
    product = cart_item.product
    product.cart_count -= cart_item.quantity  # 更新商品的購物車計數
    
    db.session.delete(cart_item)
    try:
        db.session.commit()
        return jsonify({'success': True})
    except:
        db.session.rollback()
        return jsonify({'success': False, 'message': '刪除失敗'}), 500

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    if current_user.is_store:
        return jsonify({'success': False, 'message': '店家帳號無法加入購物車'}), 403

    product = Product.query.get_or_404(product_id)
    
    # Check if product is already in cart
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first()
    
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=product_id
        )
        db.session.add(cart_item)
    
    # Initialize cart_count if it's None
    if product.cart_count is None:
        product.cart_count = 0
    
    # Update cart count
    product.cart_count += 1
    
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '已加入購物車',
            'cart_count': len(current_user.cart_items)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '加入購物車失敗'}), 500

if __name__ == '__main__':
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Create a default admin user only if it doesn't exist
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin'),
                is_store=True,
                gender='M',
                birthdate=datetime.strptime('1990-01-01', '%Y-%m-%d').date()
            )
            db.session.add(admin)
            try:
                db.session.commit()
                print("Default admin user created successfully!")
                
                # Import food data
                from food_data_reader import read_food_data, save_to_database
                
                # Read and save food data
                food_data = read_food_data('.csv')
                if (food_data is not None) and import_food_data:
                    save_to_database(food_data)
                    print("Food data imported successfully!")
                
            except Exception as e:
                db.session.rollback()
                print(f"Error during setup: {e}")
            
    app.run(host='0.0.0.0', port=8787, debug=True) 

    #9Nk44RvnZ$U3kcXN   2025hshs266@hshtw.onmicrosoft.com