import torch
import torch.nn as nn
from transformers import BertTokenizer, BertForSequenceClassification
import pandas as pd
import numpy as np
import os

# 定義模型類別
class BertForNutrition(nn.Module):
    def __init__(self, bert_model_name, num_nutrients=7):
        super().__init__()
        self.bert = BertForSequenceClassification.from_pretrained(
            bert_model_name,
            num_labels=num_nutrients,
            problem_type="regression"
        )
        
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        return outputs.logits

# 定義數據處理類別
class NutritionDataProcessor:
    def __init__(self, data_file):
        self.data = pd.read_csv(data_file)
        self.nutrient_columns = [
            'sodium_na', 'total_lipid_fat',
            'carbohydrate_by_difference', 'total_sugars',
            'fiber_total_dietary', 'energy', 'protein'
        ]
        
        # 驗證數據列是否存在
        missing_cols = [col for col in self.nutrient_columns if col not in self.data.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in dataset: {missing_cols}")
            
        # 移除全為0的行
        mask = (self.data[self.nutrient_columns] != 0).any(axis=1)
        self.data = self.data[mask]
        
        # 移除缺失值
        self.data = self.data.dropna(subset=self.nutrient_columns)
        
        # 計算標準化參數
        self.scaler = self._calculate_scaling_params()
        
    def _calculate_scaling_params(self):
        nutrients = self.data[self.nutrient_columns].values
        mean = np.mean(nutrients, axis=0)
        std = np.std(nutrients, axis=0)
        std = np.where(std == 0, 1, std)  # 避免除以0
        return {'mean': mean, 'std': std}

# 定義預測類別
class NutritionPredictor:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NutritionPredictor, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if NutritionPredictor._initialized:
            return
            
        self.model_path = r'C:\Users\chard\Desktop\chicken\best_model.pth'
        self.data_file = r"C:\Users\chard\Desktop\chicken\usda\train.csv"
        
        # 檢查文件
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Data file not found: {self.data_file}")
            
        # 設置設備
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 載入模型和tokenizer
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        self.model = BertForNutrition('bert-base-uncased')
        self.model.load_state_dict(torch.load(self.model_path))
        self.model.to(self.device)
        self.model.eval()
        
        # 載入數據和計算標準化參數
        data = pd.read_csv(self.data_file)
        self.nutrient_columns = [
            'sodium_na', 'total_lipid_fat',
            'carbohydrate_by_difference', 'total_sugars',
            'fiber_total_dietary', 'energy', 'protein'
        ]
        
        nutrients = data[self.nutrient_columns].values
        self.mean = np.mean(nutrients, axis=0)
        self.std = np.std(nutrients, axis=0)
        self.std = np.where(self.std == 0, 1, self.std)
        
        self.nutrient_names = [
            'Sodium', 'Fat', 'Carbohydrate', 
            'Sugars', 'Fiber', 'Energy', 'Protein'
        ]
        
        self.units = {
            'Sodium': 'mg',
            'Fat': 'g',
            'Carbohydrate': 'g',
            'Sugars': 'g',
            'Fiber': 'g',
            'Energy': 'kcal',
            'Protein': 'g'
        }
        
        NutritionPredictor._initialized = True
    
    def predict(self, food_name):
        """
        預測食物的營養成分
        
        Args:
            food_name (str): 食物名稱（英文）
            
        Returns:
            dict: 包含營養成分預測值的字典，格式為：
                {
                    'Sodium': {'value': float, 'unit': 'mg'},
                    ...
                }
        """
        # Tokenize
        encoding = self.tokenizer(
            food_name,
            add_special_tokens=True,
            max_length=128,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        # 移動到正確的設備
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)
        
        # 預測
        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)
        
        # 反標準化
        predictions = outputs.cpu().numpy()[0]
        denormalized = predictions * self.std + self.mean
        
        # 確保所有值非負
        denormalized = np.maximum(denormalized, 0)
        
        # 創建結果字典
        results = {}
        for name, value in zip(self.nutrient_names, denormalized):
            results[name] = {
                'value': float(value),
                'unit': self.units[name]
            }
        
        return results

def predict(food_name):
    """
    快速預測函數
    
    Args:
        food_name (str): 食物名稱（英文）
        
    Returns:
        dict: 營養成分預測結果
    
    Example:
        >>> results = predict("grilled chicken breast")
        >>> print(results['Protein']['value'])  # 蛋白質含量
        >>> print(results['Protein']['unit'])   # 單位
    """
    predictor = NutritionPredictor()
    return predictor.predict(food_name)

def print_prediction(food_name):
    """
    打印格式化的預測結果
    
    Args:
        food_name (str): 食物名稱（英文）
    """
    results = predict(food_name)
    
    print(f"\nPredicted nutrients for: {food_name}")
    print("-" * 50)
    print(f"{'Nutrient':<15} {'Amount':>10} {'Unit':<10}")
    print("-" * 50)
    
    for name in results:
        value = results[name]['value']
        unit = results[name]['unit']
        print(f"{name:<15} {value:>10.2f} {unit:<10}")

def main():
    try:
        predictor = NutritionPredictor()
        print("\nNutrition Prediction System")
        print("Enter 'quit' to exit")
        
        while True:
            food_name = input("\nEnter food name (in English): ").strip()
            if food_name.lower() == 'quit':
                break
            
            print_prediction(food_name)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Please ensure:")
        print("1. The model file exists in 'best_model.pth'")
        print("2. The data file exists and is correctly formatted")
        print("3. All required packages are installed")

if __name__ == "__main__":
    main()
