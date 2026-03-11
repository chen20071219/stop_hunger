import pandas as pd
import websockets
import asyncio
import json

async def get_recommendations(csv_data, sex, age):
    # Use secure WebSocket connection
    uri = "wss://hshgpt.webduino.tw/test_azure_api.html"
    
    # Prepare the data for the prompt
    foods = pd.read_csv(csv_data)
    
    # Create a formatted string of food information
    food_info = "Available foods with nutrition info:\n"
    for _, row in foods.iterrows():
        food_info += f"- {row['food_name']}: Energy {row['energy']}kcal, Protein {row['protein']}g, "
        food_info += f"Fat {row['total_lipid_fat']}g, Carbs {row['carbohydrate_by_difference']}g\n"
    
    prompt = f"""Based on this food list and user's information, please recommend:
    1. Top 3 healthiest individual food items
    2. Two balanced meal combinations
    user's information:
    sex: {sex}
    age: {age}
    {food_info}
    
    Please consider nutritional balance and provide brief explanations for your choices."""

    try:
        async with websockets.connect(uri, ssl=True) as websocket:
            # Send the prompt
            await websocket.send(json.dumps({"prompt": prompt}))
            
            # Process responses
            full_response = ""
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data["type"] == "start":
                    print("Starting to receive recommendations...")
                elif data["type"] == "chunk":
                    print(data["delta"], end="")
                    full_response += data["delta"]
                elif data["type"] == "end":
                    print("\nRecommendation complete!")
                    break
                elif data["type"] == "error":
                    print(f"Error: {data['message']}")
                    break
            
            return full_response.split("Azure OpenAI 回應:")[1].split("--- 回應結束")[0]

    except websockets.exceptions.InvalidStatusCode as e:
        return f"Server rejected the connection: {str(e)}"
    except websockets.exceptions.InvalidURI as e:
        return f"Invalid WebSocket URI: {str(e)}"
    except websockets.exceptions.ConnectionClosedError as e:
        return f"Connection closed unexpectedly: {str(e)}"
    except Exception as e:
        return f"An error occurred: {str(e)}"

async def main():
    try:
        csv_file = "info_food.csv"  # Your CSV file path
        result = await get_recommendations(csv_file, 'male', 20)
        print("\nFinal Recommendations:")
        print(result)
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 
