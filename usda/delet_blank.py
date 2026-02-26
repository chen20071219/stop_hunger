import pandas as pd

def delete_columns(input_file, output_file):
    # Read the CSV file
    df = pd.read_csv(input_file)
    
    # Drop the first and third columns
    df = df.drop([df.columns[2]], axis=1)
    
    # Save the modified DataFrame to a new CSV file
    df.to_csv(output_file, index=False)

if __name__ == "__main__":
    # Example usage
    input_file = r"usda\usda_food_data_filtered.csv"  # Replace with your input CSV file name
    output_file = "usda/train.csv"  # Replace with your desired output CSV file name
    
    try:
        delete_columns(input_file, output_file)
        print(f"Successfully deleted columns. Result saved to {output_file}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
