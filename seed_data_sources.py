import boto3
import os
import json
import mimetypes
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de variables
STACK_NAME = os.getenv("STACK_NAME")
AWS_PROFILE = os.getenv("AWS_PROFILE")
AWS_REGION = os.getenv("AWS_REGION")

# Archivos de Seed
S3_FILES_DIR = "resources/s3"
DYNAMO_SEED_FILE = "resources/dynamo/items.json"

# Inicializar sesión y clientes de AWS
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
cloudformation = session.client('cloudformation')
s3_client = session.client('s3')
dynamodb = session.resource('dynamodb')

def upload_files_to_s3(bucket_name, s3_client, s3_files_dir):
    """Sube archivos al bucket S3 especificado."""
    try:
        for filename in os.listdir(s3_files_dir):
            full_filename = os.path.join(s3_files_dir, filename)
            content_type, _ = mimetypes.guess_type(full_filename)
            content_type = content_type or "binary/octet-stream"

            print(f"Uploading => {filename} with content type {content_type}")
            s3_client.upload_file(full_filename, bucket_name, filename, ExtraArgs={'ContentType': content_type})
        print(f"Archivos subidos exitosamente al bucket {bucket_name}.")
    except Exception as e:
        print(f"Error al subir los archivos desde {s3_files_dir} al bucket {bucket_name}: {e}")

def insert_items_to_dynamodb(table_name, dynamodb, seed_file):
    """Inserta registros en la tabla DynamoDB especificada desde un archivo JSON."""
    try:
        with open(seed_file, 'r') as f:
            items = json.load(f)

        table = dynamodb.Table(table_name)
        for item in items:
            table.put_item(Item={
                'Id': int(item['Id']['N']),
                'Nombre': item['Nombre']['S'],
                'Cantidad': int(item['Cantidad']['N'])
            })
        print(f"Registros insertados exitosamente en la tabla {table_name}.")
    except Exception as e:
        print(f"Error al insertar registros en la tabla {table_name}: {e}")

if __name__ == "__main__":
    try:
        response = cloudformation.describe_stacks(StackName=STACK_NAME)
        outputs = response["Stacks"][0]["Outputs"]

        for output in outputs:
            if "S3Bucket" in output["OutputKey"]:
                bucket_name = output["OutputValue"]
                print(f"Subiendo archivos a S3 bucket: {bucket_name}")
                upload_files_to_s3(bucket_name, s3_client, S3_FILES_DIR)

            if "DynamoDBTable" in output["OutputKey"]:
                table_name = output["OutputValue"]
                print(f"Insertando registros en DynamoDB table: {table_name}")
                insert_items_to_dynamodb(table_name, dynamodb, DYNAMO_SEED_FILE)

    except cloudformation.exceptions.ClientError as e:
        print(f"Error al describir el stack '{STACK_NAME}': {e}")
