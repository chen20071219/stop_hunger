import requests
import pandas as pd
import time
import os

API_KEY = "FYHVhBIADmddIvqRTQDJfVlW3CXtWraCOZ70pcLQ"
CSV_FILE = "usda/usda_food_data_filtered.csv"
t1 = time.time()
# 讀取需要查詢的食物ID
file_path = "usda/demand.txt"
with open(file_path, "r", encoding="utf-8") as f:
    food_ids = [line.strip() for line in f]

url_template = "https://api.nal.usda.gov/fdc/v1/food/{food_id}?api_key={api_key}"

# 定義主要營養素
main_nutrients = {
    "Water": "water",
    "Energy": "energy",
    "Protein": "protein",
    "Total lipid (fat)": "total_lipid_fat",
    "Carbohydrate, by difference": "carbohydrate_by_difference",
    "Fiber, total dietary": "fiber_total_dietary",
    "Total Sugars": "total_sugars",
    "Sodium, Na": "sodium_na"
}

# 讀取現有的CSV文件（如果存在）
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    print(f"已載入現有CSV文件，目前有 {len(df)} 筆資料")
else:
    df = pd.DataFrame(columns=["food_id", "食物名稱"] + list(main_nutrients.values()))
    print("創建新的CSV文件")

# 從現有數據中獲取已處理的食物ID
fetched_foods = set(df['food_id'].astype(str).values) if 'food_id' in df.columns else set()
print(f"已有 {len(fetched_foods)} 個食物ID記錄")

def save_to_csv(food_data, food_id):
    """將新的食物數據添加到CSV文件"""
    global df
    # 添加food_id到數據中
    food_data['food_id'] = food_id
    
    # 創建新的一行數據
    new_row = pd.DataFrame([food_data])
    
    # 添加到現有DataFrame
    df = pd.concat([df, new_row], ignore_index=True)
    
    # 重新排列列的順序，確保food_id在最前面
    columns = ['food_id', '食物名稱'] + list(main_nutrients.values())
    df = df[columns]
    
    # 保存整個DataFrame
    df.to_csv(CSV_FILE, index=False)
    print(f"已將 {food_data['食物名稱']} (ID: {food_id}) 添加到CSV文件，目前共 {len(df)} 筆資料")

def get_food_data(food_id):
    """獲取單個食物的營養數據"""
    # 首先檢查food_id是否已存在
    if str(food_id) in fetched_foods:
        print(f"食物 ID {food_id} 已存在於CSV中，跳過API請求...")
        return None
        
    try:
        # 獲取 USDA 食品數據
        url = url_template.format(food_id=food_id, api_key=API_KEY)
        response = requests.get(url)
        data = response.json()

        time.sleep(2.75)  # API 請求間隔
        if "foodNutrients" not in data:
            print(f"食物 ID {food_id} 獲取失敗！")
            return None

        # 提取主要營養素
        food_data = {"食物名稱": data["description"]}
        for key in main_nutrients.values():
            food_data[key] = None  # 預先填充為空值

        for nutrient in data["foodNutrients"]:
            nutrient_name = nutrient["nutrient"]["name"]
            if nutrient_name in main_nutrients:
                food_data[main_nutrients[nutrient_name]] = nutrient["amount"]

        # 如果有空值，使用0填充
        for key in main_nutrients.values():
            if food_data[key] is None:
                food_data[key] = 0
                

        return food_data

    except Exception as e:
        print(f"處理食物 ID {food_id} 時發生錯誤: {str(e)}")
        return None

def main(t1):
    # 轉成可變動的 list
    remaining_foods = list(food_ids)
    for food_id in food_ids:
        food_data = get_food_data(food_id)
        print(round(time.time()-t1, 3),time.ctime(), end=" ")
        t1 = time.time()
        # 不論成功或失敗都要移除
        remaining_foods.remove(food_id)
        with open(file_path, "w", encoding="utf-8") as f:
            for fid in remaining_foods:
                f.write(f"{fid}\n")
        if food_data is None:
            print(f"食物 ID {food_id} 處理失敗或已存在，已從 demand.txt 移除")
            continue
        save_to_csv(food_data, food_id)
        fetched_foods.add(str(food_id))
        print(f"成功獲取 {food_data['食物名稱']}，已從 demand.txt 移除")

    print("所有食物數據處理完成！")
    print(f"已從 demand.txt 移除已存在及成功獲取或失敗的 food_id，剩餘 {len(remaining_foods)} 筆待處理。")

if __name__ == "__main__":
    
    main(time.time())


