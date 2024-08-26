import boto3
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de variables
STACK_NAME = os.getenv("STACK_NAME")
AWS_PROFILE = os.getenv("AWS_PROFILE")
AWS_REGION = os.getenv("AWS_REGION")

def get_stack_info(cf, stack_name):
    """Verifica la existencia y estado del stack en CloudFormation."""
    try:
        stack = cf.describe_stacks(StackName=stack_name)
        stack_status = stack['Stacks'][0]['StackStatus']
        if "COMPLETE" in stack_status:
            return stack['Stacks'][0]
        return None
    except cf.exceptions.ClientError as e:
        if 'does not exist' in str(e):
            return None
        print(f"Error al verificar el stack: {e}")
        sys.exit(1)

def delete_s3_objects(s3, bucket_name):
    """Elimina todos los objetos y versiones de objetos en un bucket S3."""
    bucket = s3.Bucket(bucket_name)
    bucket.objects.all().delete()
    bucket.object_versions.all().delete()
    print(f"Todos los objetos y versiones en el bucket '{bucket_name}' han sido eliminados.")

def delete_dynamodb_items(dynamodb, table_name):
    """Elimina todos los elementos en una tabla DynamoDB."""
    table = dynamodb.Table(table_name)
    items = table.scan().get('Items', [])
    for item in items:
        table.delete_item(Key={'Id': item['Id'], 'Nombre': item['Nombre']})
    print(f"Eliminados {len(items)} registros de la tabla '{table_name}'.")

if __name__ == "__main__":
    # Inicializar sesión y clientes de AWS
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    cloudformation = session.client('cloudformation')
    s3 = session.resource('s3')
    dynamodb = session.resource('dynamodb')
    
    # Obtener información del stack
    stack = get_stack_info(cloudformation, STACK_NAME)
    
    if not stack:
        print(f"El stack '{STACK_NAME}' no existe o no ha sido creado correctamente.")
        sys.exit(1)
    
    if stack['StackStatus'] not in ["CREATE_COMPLETE", "UPDATE_COMPLETE", "ROLLBACK_COMPLETE"]:
        print(f"El stack '{STACK_NAME}' no está en un estado válido para obtener Outputs. Estado actual: {stack['StackStatus']}")
        sys.exit(1)
    
    outputs = stack.get("Outputs", [])
    
    if not outputs:
        print(f"El stack '{STACK_NAME}' no tiene Outputs.")
        sys.exit(0)
    
    # Procesar los outputs del stack
    for output in outputs:
        if "S3Bucket" in output["OutputKey"]:
            delete_s3_objects(s3, output["OutputValue"])
        
        if "DynamoDBTable" in output["OutputKey"]:
            delete_dynamodb_items(dynamodb, output["OutputValue"])
