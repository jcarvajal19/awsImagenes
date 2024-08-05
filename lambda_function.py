 
import json
import base64
import io
import requests
import boto3
import uuid 
import logging
import hashlib
from dotenv import load_dotenv

# Configuración de logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

import os
# Cargar las variables de entorno desde el archivo .env
load_dotenv()
# Acceder a las variables de entorno
OPENIA_KEY = os.getenv('OPENIA_KEY')

def lambda_handler(event, context):
    image_data = base64.b64decode(event['Image'])
    logger.info(f"Event received: {event}")
    logger.info(f"Received image with size: {len(image_data)} bytes")
    bucket_name = "identificacionimagenes"  
    received_checksum = event['Checksum']
           
    # Calculate checksum
    calculated_checksum = hashlib.md5(image_data).hexdigest()
         
    try: 
        # Verificar el tamaño de la imagen
        if len(image_data) > 20 * 1024 * 1024:  # 20 MB
            raise ValueError("La imagen supera el tamaño permitido de 20 MB")
        
        # Valid extensions for OpenAI
        valid_extensions = ['png', 'jpeg', 'gif', 'webp']
        
        # Get the extension of the image from the event
        extensionFile = event.get('Extension', 'jpeg').lower()
        
        logger.info(f"Image extension: {extensionFile}")
         
        key = f"upload/{uuid.uuid4()}.{extensionFile}"
        s3_client.put_object(Body=image_data, Bucket=bucket_name, Key=key)
        
        image_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        
        logger.info(f"Image uploaded to S3: {image_url}")
        
        # Verify checksum
        if received_checksum != calculated_checksum:
            raise ValueError(f"el checksum no coincide. llegada:{received_checksum} - actual:{calculated_checksum}")
        
        if extensionFile not in valid_extensions:
            raise ValueError(f"Unsupported image format. Supported formats are: png, jpeg, gif, webp: -{extensionFile}-")
        resultado = generar_texto_con_gpt4(image_url)
        return {
            'statusCode': 200,
            'body': json.dumps(resultado)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({"error": str(e)})
        }

def generar_texto_con_gpt4(image_url):
    api_key = OPENIA_KEY
    #prompt = f"Analiza la image y si el objeto principal detectado es una o varias 'BOTELLA(s) DE VIVE100' devuelve solo la palabra TRUE, de lo contrario devuelve la palabra FALSE"
    prompt = f"Analiza la image y si el objeto principal detectado es una o varias 'BOTELLA(s) DE VIVE100' devuelve 0 si no hay botellas o devuelve el numero que se detectaron. En resumen, la respuesta debe ser solo numerica de los elementos encontrados."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
    "model": "gpt-4o-mini",
    "messages": [
        {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"{prompt}" 
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url
                }
            }
        ]
        }
    ],
    "max_tokens": 100
    }

    logger.info(f"Request payload: {payload}")
    
    try:
        logger.info(f"Sending request to OpenAI API")
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        valjson = response.json()
        
        logger.info(f"Response from OpenAI API: {valjson}")
        
        if "choices" in valjson and len(valjson["choices"]) > 0:
            response = valjson["choices"][0]["message"]["content"]
            logger.info(f"Response from OpenAI API: {response}")
            return response
        else:
            return "La respuesta de la API no contiene la estructura esperada."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en la solicitud a la API: {e}")
        try:
            error_response = e.response.json()
        except ValueError:
            error_response = e.response.text
        
        return {
            "error": "Error en la solicitud a la API",
            "details": error_response
        }

