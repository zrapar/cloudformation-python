import requests
import json
import os
import sys
from dotenv import load_dotenv
import argparse

# Cargar variables de entorno
load_dotenv()

# Configuración de variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_message(message):
    """Envía un mensaje a un chat de Telegram."""
    url = f"https://api.telegram.org/{BOT_TOKEN}/sendMessage"
    
    payload = json.dumps({
        "chat_id": str(CHAT_ID),
        "text": message,
        "parse_mode": "Markdown"
    })
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, headers=headers, data=payload)
    response_data = response.json()
    
    if response_data.get('ok'):
        print("Message Sent")
    else:
        error_description = response_data.get('description', 'Unknown error occurred')
        raise Exception(f"Problem sending message: {error_description}")

def parse_arguments():
    """Parsea los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(description='Enviar un mensaje a Telegram.')
    parser.add_argument('--message', required=True, help='El mensaje a enviar a Telegram.')
    args = parser.parse_args()
    return args.message

if __name__ == "__main__":
    try:
        message = parse_arguments()
        send_message(message)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
