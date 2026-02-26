import pandas as pd
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import json
from flask_login import UserMixin

# 初始化 Flask 應用程式和資料庫
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "food_platform.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 定義使用者模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_store = db.Column(db.Boolean, default=False)
    gender = db.Column(db.String(1))
    birthdate = db.Column(db.Date)

# 定義食物資料模型 (與 app.py 中的 Product 模型相對應)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    expiry_date = db.Column(db.DateTime, nullable=False)
    original_price = db.Column(db.Float, nullable=False)
    discount_rate = db.Column(db.Float, nullable=False)
    nutrition_info = db.Column(db.JSON)
    store_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def create_admin_user():
    """創建管理員用戶"""
    with app.app_context():
        # 檢查是否已存在管理員
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin'),
                is_store=True,
                gender='M',
                birthdate=datetime.strptime('1990-01-01', '%Y-%m-%d').date()
            )
            db.session.add(admin)
            db.session.commit()
            print("已創建管理員用戶")
        return admin.id

def read_food_data(file_path='.csv'):
    """
    讀取食物資料清單
    
    Args:
        file_path (str): CSV檔案的路徑
        
    Returns:
        pd.DataFrame: 包含食物資料的DataFrame
    """
    try:
        # 檢查檔案是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"找不到檔案: {file_path}")
            
        # 讀取CSV檔案
        df = pd.read_csv(file_path)
        
        # 顯示基本資訊
        print(f"成功讀取 {len(df)} 筆食物資料")
        print("\n資料欄位:")
        for column in df.columns:
            print(f"- {column}")
            
        return df
        
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {str(e)}")
        return None

def save_to_database(df):
    """
    將DataFrame資料儲存到資料庫
    
    Args:
        df (pd.DataFrame): 食物資料DataFrame
    """
    if df is None:
        return
        
    try:
        with app.app_context():
            # 確保資料表存在
            db.create_all()
            
            # 確保管理員用戶存在
            admin_id = create_admin_user()
            
            # 設定預設值
            default_quantity = 10
            default_address = "none"
            default_expiry_date = datetime.now() + timedelta(days=7)
            default_original_price = 100.0
            default_discount_rate = 0.8
            
            # 新增資料
            for _, row in df.iterrows():
                # 準備營養成分資料
                nutrition_info = {
                    'energy': float(row['energy']),
                    'protein': float(row['protein']),
                    'fat': float(row['total_lipid_fat']),
                    'carbohydrate': float(row['carbohydrate_by_difference']),
                    'fiber': float(row['fiber_total_dietary']),
                    'sugars': float(row['total_sugars']),
                    'sodium': float(row['sodium_na'])
                }
                
                # 創建新的Product實例
                product = Product(
                    name=row['食物名稱'],
                    quantity=default_quantity,
                    address=default_address,
                    latitude=float(row['latitude']),
                    longitude=float(row['longitude']),
                    expiry_date=default_expiry_date,
                    original_price=default_original_price,
                    discount_rate=default_discount_rate,
                    nutrition_info=nutrition_info,
                    store_id=admin_id
                )
                db.session.add(product)
            
            # 提交變更
            db.session.commit()
            print(f"\n成功將 {len(df)} 筆資料儲存到資料庫")
            
    except Exception as e:
        print(f"儲存資料時發生錯誤: {str(e)}")
        db.session.rollback()

def verify_database():
    """
    驗證資料庫內容
    """
    try:
        with app.app_context():
            products = Product.query.all()
            print("\n資料庫內容驗證:")
            print(f"資料庫中共有 {len(products)} 筆食物資料")
            print("\n前5筆資料:")
            for product in products[:5]:
                print(f"- {product.name}: {product.nutrition_info['energy']}kcal, 蛋白質{product.nutrition_info['protein']}g")
    except Exception as e:
        print(f"查詢資料庫時發生錯誤: {str(e)}")

def get_food_statistics(df):
    """
    計算並顯示食物資料的基本統計資訊
    
    Args:
        df (pd.DataFrame): 食物資料DataFrame
    """
    if df is None:
        return
        
    print("\n基本統計資訊:")
    print(f"平均熱量: {df['energy'].mean():.2f} kcal")
    print(f"平均蛋白質: {df['protein'].mean():.2f} g")
    print(f"平均脂肪: {df['total_lipid_fat'].mean():.2f} g")
    print(f"平均碳水化合物: {df['carbohydrate_by_difference'].mean():.2f} g")

if __name__ == "__main__":
    # 讀取食物資料
    food_data = read_food_data()
    
    # 顯示統計資訊
    if food_data is not None:
        get_food_statistics(food_data)
        
        # 儲存到資料庫
        save_to_database(food_data)
        
        # 驗證資料庫內容
        verify_database() 
