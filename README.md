# Introduction

## 專案背景與動機

隨著永續發展與食物浪費議題日益受到重視，許多即期品（即將到期的食品）常因銷售不及而被丟棄，造成資源浪費與環境負擔。本專案旨在打造一個結合「即期品推廣」、「營養健康推薦」與「AI 智能預測」的全方位平台，協助店家有效銷售即期品，同時讓消費者以優惠價格獲得健康、合適的食品選擇。

---

## 主要功能與特色

### 1. 用戶系統
- 支援消費者與店家兩種角色註冊、登入、權限分流。
- 消費者可瀏覽、搜尋、購買商品，店家可上架、管理商品。
- 用戶資料包含性別、生日，作為個人化推薦依據。

### 2. 商品管理與即期品推廣
- 店家可新增商品，設定數量、價格、折扣、地點、到期日、營養資訊。
- 商品支援地理座標，方便地圖顯示與距離搜尋。
- 商品資訊包含營養成分（熱量、蛋白質、脂肪、碳水、纖維、鈉等）。

### 3. 地理搜尋與地圖整合
- 消費者可依據關鍵字、最高價格、距離等條件搜尋商品。
- 整合 geopy 與 Leaflet.js，顯示商品地點、距離與地圖標記。
- 支援自動偵測用戶位置，提升搜尋精準度。

### 4. AI 營養成分預測
- 內建 BERT 模型，能根據食物名稱自動預測其七大營養成分。
- 支援批次資料訓練與即時預測，協助店家快速補全商品營養資訊。
- 預測欄位：Sodium, Fat, Carbohydrate, Sugars, Fiber, Energy, Protein。

### 5. 個人化營養推薦
- 根據用戶年齡、性別自動計算每日營養需求（參考台灣 DRIs）。
- 提供「個別商品推薦」與「套餐組合推薦」兩種模式。
- 推薦演算法考量用戶需求、商品營養成分、價格、距離等多重因素。

### 6. 購物車與下單流程
- 消費者可將商品加入購物車，調整數量、刪除、結帳。
- 購物車數量即時顯示於導覽列。

### 7. 資料管理與匯入
- 支援 CSV 食品資料匯入，並自動寫入資料庫。
- 內建管理員帳號，方便初始測試與資料驗證。

---

## 技術架構與資料流

### 架構總覽

#### 1. 後端框架
- **Flask (v3.0.2)**
  - 輕量級 Web 框架，採用 RESTful API 設計
  ```1:5:app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
  ```
  - 路由處理：使用裝飾器管理 API 端點
  ```107:111:app.py
@app.route('/')
def index():
    # 獲取搜尋參數
    search = request.args.get('search', '').strip()
    max_price = request.args.get('max_price', type=float)
  ```
  - 回應格式：支援 JSON API 與 HTML 模板渲染
  ```318:328:app.py
@app.route('/predict_nutrition', methods=['POST'])
def predict_nutrition():
    try:
        data = request.get_json()
        food_name = data.get('food_name')
        
        if not food_name:
            return jsonify({'success': False, 'error': '請提供食物名稱'})

        # 使用 predict.py 中的預測函數
        nutrition_values = predict(food_name)
  ```

- **Flask-SQLAlchemy (v3.1.1)**
  - ORM 框架：定義資料模型與關聯
  ```28:39:app.py
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
  ```
  - 關聯處理：一對多、多對多關係
  ```82:91:app.py
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
    product = db.relationship('Product', backref=db.backref('cart_items', lazy=True))
  ```

- **Flask-Login (v0.6.3)**
  - 使用者認證：登入、登出功能
  ```205:215:app.py
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
  ```
  - 權限控制：用戶角色區分
  ```334:337:app.py
@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_store:
  ```

#### 2. 資料庫
- **SQLite**
  - 資料庫配置
  ```16:20:app.py
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///food_platform.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
  ```
  - 資料庫初始化與遷移
  ```766:776:app.py
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
  ```

#### 3. AI/ML 技術棧
- **營養成分預測系統**
  - 預測 API 實作
  ```318:334:app.py
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
  ```

- **個人化推薦系統**
  - 營養需求計算
  ```93:106:app.py
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
  ```

#### 4. 地理資訊服務
- **geopy (v2.4.1)**
  - 地理編碼實作
  ```222:231:app.py
def get_coordinates(address):
    try:
        geolocator = Nominatim(user_agent="my_food_platform")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        return None, None
    except GeocoderTimedOut:
        return None, None
  ```
  - 距離計算與搜尋
  ```134:148:app.py
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
  ```

#### 5. 前端技術
- **模板與路由整合**
  - 首頁路由與模板渲染
  ```107:120:app.py
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
  ```

- **購物車功能**
  - 購物車操作 API
  ```589:612:app.py
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
  ```

- **商品管理介面**
  - 商品新增功能
  ```334:348:app.py
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
  ```

#### 6. 開發工具與環境
- **資料庫遷移工具**
  ```15:15:app.py
from flask_migrate import Migrate
  ```
  ```19:19:app.py
migrate = Migrate(app, db)
  ```

- **密碼安全處理**
  - 密碼雜湊與驗證
  ```205:215:app.py
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
  ```

- **開發伺服器配置**
  ```775:775:app.py
    app.run(host='0.0.0.0', port=8787, debug=True) 
  ```

### 主要資料流
1. **商品上架**：店家填寫商品資訊 → 若缺營養成分可用 AI 預測自動補全 → 寫入資料庫。
2. **消費者搜尋**：輸入條件（關鍵字、價格、距離）→ 後端查詢商品 → 回傳結果並顯示於地圖。
3. **個人化推薦**：用戶點擊「取得推薦」→ 後端根據用戶資料與商品營養成分計算推薦分數 → 回傳推薦清單。
4. **AI 預測**：輸入食物名稱 → BERT 模型預測營養成分 → 回傳預測值。
5. **購物車/下單**：用戶將商品加入購物車 → 調整數量/結帳 → 更新庫存。

---

## AI 模型細節

- **模型架構**：採用 HuggingFace Transformers 的 BERT-base-uncased，將食物名稱作為輸入，回歸預測七項營養素。
- **訓練資料**：來自 usda/train.csv，包含多筆食物名稱與對應營養成分。
- **訓練流程**：
  - 文字經 BERT tokenizer 處理，餵入 BERT，最後一層接回歸頭（num_labels=7）。
  - 損失函數為 MSELoss。
  - 支援 GPU/CPU 訓練。
- **預測流程**：
  - 輸入食物名稱 → tokenizer → BERT → 輸出七項營養素預測值。
  - 支援批次預測與單筆即時預測。

---

## 使用流程

1. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```
2. **資料庫初始化與資料匯入**
   ```bash
   python food_data_reader.py
   ```
   - 會自動建立資料庫、管理員帳號並匯入食物資料。
3. **啟動平台**
   ```bash
   python app.py
   ```
   - 預設於 http://127.0.0.1:5000/
4. **AI 模型訓練/測試**
   ```bash
   cd train
   python main.py
   ```
   - 可自訂訓練資料路徑與參數。

---

## 目標族群
- 想以優惠價格購買即期品的消費者
- 希望減少食物浪費、推廣永續消費的店家
- 需要根據個人健康需求選擇食品的族群

---

## 未來展望
- 支援多語系介面（中/英）
- 推出行動裝置版（PWA）
- 擴充支付、物流、通知等功能
- 強化推薦演算法（考慮過敏原、疾病、飲食偏好等）
- 與更多即期品供應商串接，擴大資料來源

---

## 聯絡方式
如需協助、回饋或合作，請聯絡專案維護者。 
---

由於 best_model.pth 自定義模型檔案過大，無法上傳。
