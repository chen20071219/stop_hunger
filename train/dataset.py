import torch
from torch.utils.data import Dataset
import pandas as pd
import numpy as np

class FoodDataset(Dataset):
    def __init__(self, data_file, tokenizer, max_length=128):
        """
        Args:
            data_file (str): USDA format CSV file path
            tokenizer: BERT tokenizer
            max_length (int): Maximum sequence length
        """
        # Read the CSV file
        self.data = pd.read_csv(data_file)
        print(f"Original dataset size: {len(self.data)}")
        
        # Nutrient columns
        self.nutrient_columns = [
            'sodium_na', 'total_lipid_fat',
            'carbohydrate_by_difference', 'total_sugars',
            'fiber_total_dietary', 'energy', 'protein'
        ]
        
        # Validate columns exist
        missing_cols = [col for col in self.nutrient_columns if col not in self.data.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in dataset: {missing_cols}")
            
        # Remove rows where all nutrient values are 0
        mask = (self.data[self.nutrient_columns] != 0).any(axis=1)
        self.data = self.data[mask]
        print(f"Dataset size after removing zero-value rows: {len(self.data)}")
        
        # Remove rows with missing values
        self.data = self.data.dropna(subset=self.nutrient_columns)
        print(f"Dataset size after removing rows with missing values: {len(self.data)}")
        
        self.tokenizer = tokenizer
        self.max_length = max_length
        
        # Print value ranges for each nutrient
        self._print_nutrient_stats()
        
        # Standardize nutrient data
        self.scaler = self._fit_scaler()

    def _print_nutrient_stats(self):
        """Print statistics for each nutrient"""
        print("\nNutrient Statistics:")
        for col in self.nutrient_columns:
            stats = self.data[col].describe()
            print(f"\n{col}:")
            print(f"  Min: {stats['min']:.2f}")
            print(f"  Max: {stats['max']:.2f}")
            print(f"  Mean: {stats['mean']:.2f}")
            print(f"  Std: {stats['std']:.2f}")

    def _fit_scaler(self):
        """Calculate and return statistics for standardization"""
        nutrients = self.data[self.nutrient_columns].values
        mean = np.mean(nutrients, axis=0)
        std = np.std(nutrients, axis=0)
        # Avoid division by zero
        std = np.where(std == 0, 1, std)
        return {'mean': mean, 'std': std}

    def _normalize_nutrients(self, nutrients):
        """Standardize nutrient data"""
        return (nutrients - self.scaler['mean']) / self.scaler['std']

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        # Get English food name from the first column
        food_name = str(self.data.iloc[idx].iloc[0])
        nutrients = self.data.iloc[idx][self.nutrient_columns].values.astype(np.float32)
        
        # Standardize nutrients
        nutrients_normalized = self._normalize_nutrients(nutrients)

        # Convert food name to BERT input format
        encoding = self.tokenizer(
            food_name,
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'nutrients': torch.tensor(nutrients_normalized, dtype=torch.float32)
        }
        
    def get_scaler(self):
        """Return the scaler for denormalization"""
        return self.scaler 
