from transformers import BertTokenizer, BertForSequenceClassification, BertConfig
import torch
from dataset import FoodDataset
from torch.utils.data import random_split
import torch.nn as nn
import os
import numpy as np
import time
from tqdm import tqdm

# Define data file path
DATA_FILE = r"C:\Users\chard\Desktop\chicken\usda\train.csv"

# Create necessary directories
os.makedirs('results', exist_ok=True)

# Custom BERT model for nutrition prediction
class BertForNutrition(nn.Module):
    def __init__(self, bert_model_name, num_nutrients=7):  # 更新為7個營養成分
        super().__init__()
        self.bert = BertForSequenceClassification.from_pretrained(
            bert_model_name,
            num_labels=num_nutrients,
            problem_type="regression"
        )
        
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        return outputs.logits

# Use English BERT model
model_name = "bert-base-uncased"  # Changed to English BERT
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertForNutrition(model_name)

# Ensure the data file exists
if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"Data file not found at: {DATA_FILE}")

# Load dataset
dataset = FoodDataset(DATA_FILE, tokenizer)
scaler = dataset.get_scaler()  # Get the scaler for denormalization

# Split into train and validation sets
train_size = int(0.8 * len(dataset))
val_size = len(dataset) - train_size
train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

print(f"Training set size: {train_size}")
print(f"Validation set size: {val_size}")

# Custom training loop
def train_model(model, train_dataset, val_dataset, num_epochs=5, batch_size=8, learning_rate=2e-5):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    model.to(device)
    
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()
    
    best_val_loss = float('inf')
    
    # Create progress bar for epochs
    epoch_pbar = tqdm(range(num_epochs), desc="Training Progress", position=0)
    
    for epoch in epoch_pbar:
        # Training phase
        model.train()
        total_loss = 0
        
        # Create progress bar for batches
        train_pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{num_epochs}", 
                         leave=False, position=1)
        
        for batch in train_pbar:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            nutrients = batch['nutrients'].to(device)
            
            optimizer.zero_grad()
            outputs = model(input_ids, attention_mask)
            loss = criterion(outputs, nutrients)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            train_pbar.set_postfix({'loss': f'{loss.item():.4f}'})
        
        avg_train_loss = total_loss / len(train_loader)
        
        # Validation phase
        model.eval()
        val_loss = 0
        val_pbar = tqdm(val_loader, desc="Validation", leave=False, position=1)
        
        with torch.no_grad():
            for batch in val_pbar:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                nutrients = batch['nutrients'].to(device)
                
                outputs = model(input_ids, attention_mask)
                loss = criterion(outputs, nutrients)
                val_loss += loss.item()
                val_pbar.set_postfix({'loss': f'{loss.item():.4f}'})
        
        avg_val_loss = val_loss / len(val_loader)
        epoch_pbar.set_postfix({
            'train_loss': f'{avg_train_loss:.4f}',
            'val_loss': f'{avg_val_loss:.4f}'
        })
        
        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), 'results/best_model.pth')
            print("\nSaved new best model")

# Train model
train_model(model, train_dataset, val_dataset)

# Model evaluation
def evaluate_model(model, dataset):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    
    loader = torch.utils.data.DataLoader(dataset, batch_size=8)
    criterion = nn.MSELoss(reduction='none')
    
    total_mse = 0
    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            nutrients = batch['nutrients'].to(device)
            
            outputs = model(input_ids, attention_mask)
            mse = criterion(outputs, nutrients)
            total_mse += mse.mean(dim=0)
    
    avg_mse = total_mse / len(loader)
    print("\nMean Squared Error per nutrient:")
    nutrient_names = ['Sodium', 'Fat', 'Carbohydrate', 'Sugars', 'Fiber', 'Energy', 'Protein']
    for name, error in zip(nutrient_names, avg_mse.cpu().numpy()):
        print(f"{name}: {error:.4f}")

# Evaluate model
evaluate_model(model, val_dataset)

# Function to predict nutrients for a new food item
def predict_nutrients(model, tokenizer, food_name):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    
    # Tokenize the food name
    encoding = tokenizer(
        food_name,
        add_special_tokens=True,
        max_length=128,
        padding='max_length',
        truncation=True,
        return_tensors='pt'
    )
    
    input_ids = encoding['input_ids'].to(device)
    attention_mask = encoding['attention_mask'].to(device)
    
    # Get predictions
    with torch.no_grad():
        outputs = model(input_ids, attention_mask)
    
    # Denormalize predictions
    predictions = outputs.cpu().numpy()[0]
    denormalized_predictions = predictions * scaler['std'] + scaler['mean']
    
    # Print predictions
    nutrient_names = ['Sodium', 'Fat', 'Carbohydrate', 'Sugars', 'Fiber', 'Energy', 'Protein']
    print(f"\nPredicted nutrients for {food_name}:")
    for name, value in zip(nutrient_names, denormalized_predictions):
        print(f"{name}: {value:.2f}")
    
    return denormalized_predictions

# Example usage
print("\nExample predictions:")
predict_nutrients(model, tokenizer, "apple")
