import boto3
import sys
import subprocess
import os
import time
from dotenv import load_dotenv
import json

# Cargar variables de entorno
load_dotenv()

# Configuración de variables
STACK_NAME = os.getenv("STACK_NAME")
AWS_PROFILE = os.getenv("AWS_PROFILE")
AWS_REGION = os.getenv("AWS_REGION")
VPC_ID = os.getenv("VPC_ID")

# Variables de configuración
TEMPLATE_FILE = "config/cloudformation.yaml"
PARAMETERS = {
    "S3WebBucketName": "s3-amatium-test-rafael",
    "StageName": "api"
}

# Argumento CLI para el seed
seed = False

def format_parameters(params):
    """Formatea los parámetros para CloudFormation."""
    return [{'ParameterKey': k, 'ParameterValue': v} for k, v in params.items()]

def get_subnet_ids(ec2_client, vpc_id):
    """Obtiene los IDs de las subnets asociadas a un VPC."""
    response = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    return [subnet['SubnetId'] for subnet in response['Subnets']]

def get_security_group(ec2_client, group_name='vpc-endpoint-sg'):
    """Obtiene el ID del grupo de seguridad especificado."""
    response = ec2_client.describe_security_groups(Filters=[{'Name': 'group-name', 'Values': [group_name]}])
    return response['SecurityGroups'][0]['GroupId']

def parse_arguments():
    """Parsea los argumentos de la línea de comandos."""
    global seed
    args = sys.argv[1:]
    seed = "--seed" in args

def stack_exists(cloudformation_client, stack_name):
    """Verifica si el stack ya existe y está en un estado válido."""
    try:
        stack = cloudformation_client.describe_stacks(StackName=stack_name)
        return "COMPLETE" in stack['Stacks'][0]['StackStatus']
    except cloudformation_client.exceptions.ClientError as e:
        if 'does not exist' in str(e):
            return False
        print(f"Error al verificar el stack: {e}")
        sys.exit(1)

def create_stack(cloudformation_client, stack_name, template_name, params):
    """Crea un stack en CloudFormation."""
    print(f"Creando el stack {stack_name}...")
    cloudformation_client.create_stack(
        StackName=stack_name,
        TemplateBody=open(template_name).read(),
        Capabilities=['CAPABILITY_NAMED_IAM'],
        Parameters=params
    )
    return cloudformation_client.get_waiter('stack_create_complete')

def update_stack(cloudformation_client, stack_name, template_name, params):
    """Actualiza un stack existente en CloudFormation."""
    print(f"El stack {stack_name} ya existe. Actualizando...")
    cloudformation_client.update_stack(
        StackName=stack_name,
        TemplateBody=open(template_name).read(),
        Capabilities=['CAPABILITY_NAMED_IAM'],
        Parameters=params
    )
    return cloudformation_client.get_waiter('stack_update_complete')

def handle_seed_data(seed, stack_exists):
    """Maneja el proceso de seed de datos."""
    if seed:
        if stack_exists:
            print("Borrando información antigua...\n")
            subprocess.check_call(['python', 'delete_seed_sources.py'])
        print("Llenando la información necesaria para su funcionamiento\n")
        subprocess.check_call(['python', 'seed_data_sources.py'])

def invalidate_cloudfront(cloudformation_client, stack_name, session):
    """Invalidar el cache de CloudFront basado en el Output del stack y actualizar la política de API Gateway."""
    response = cloudformation_client.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]
    cloudfront_distribution_id = None

    for output in outputs:
        if output['OutputKey'] == "CloudFrontID":
            cloudfront_distribution_id = output['OutputValue']
            cf = session.client('cloudfront')
            cf.create_invalidation(
                DistributionId=cloudfront_distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': 1,
                        'Items': ["/*"]
                    },
                    'CallerReference': str(time.time()).replace(".", "")
                }
            )

    print(f"{output['OutputKey']} = {output['OutputValue']}")

def main():
    parse_arguments()

    # Configuración de la sesión de boto3
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    cloudformation_client = session.client('cloudformation')
    ec2_client = session.client('ec2')

    # Obtener la lista de subnets y el ID del grupo de seguridad
    subnet_ids = get_subnet_ids(ec2_client, VPC_ID)
    sg_id = get_security_group(ec2_client)

    # Agregar la lista de subnets y el ID del grupo de seguridad a los parámetros
    PARAMETERS["SubnetIds"] = ','.join(subnet_ids)
    PARAMETERS["VpcEndpointSgId"] = sg_id
    
    formatted_params = format_parameters(PARAMETERS)
    stack_exists_flag = stack_exists(cloudformation_client, STACK_NAME)

    # Crear o actualizar el stack
    if stack_exists_flag:
        waiter = update_stack(cloudformation_client, STACK_NAME, TEMPLATE_FILE, formatted_params)
    else:
        waiter = create_stack(cloudformation_client, STACK_NAME, TEMPLATE_FILE, formatted_params)

    # Esperar a que el stack se complete
    try:
        waiter.wait(StackName=STACK_NAME)
        message_ok = f"El stack {STACK_NAME} se ha creado/actualizado exitosamente en la región {AWS_REGION}."
        print(message_ok)
        handle_seed_data(seed, stack_exists_flag)
        invalidate_cloudfront(cloudformation_client, STACK_NAME, session)
        subprocess.call(['python', 'send_message.py', '--message', message_ok])
    except Exception as e:
        print(e)
        message_error = f"Error al crear/actualizar el stack {STACK_NAME} en la región {AWS_REGION}."
        print(message_error)
        print("Revisando los eventos del stack para más detalles...\n")

        events = cloudformation_client.describe_stack_events(StackName=STACK_NAME)['StackEvents']
        failed_events = [event for event in events if 'FAILED' in event['ResourceStatus']]
        for event in failed_events:
            print(event['ResourceStatusReason'])

        # Verificar si el stack está en estado ROLLBACK_COMPLETE
        stack_status = cloudformation_client.describe_stacks(StackName=STACK_NAME)['Stacks'][0]['StackStatus']
        if stack_status == 'ROLLBACK_COMPLETE':
            print(f"El stack está en estado {stack_status}. Procediendo a eliminarlo...\n")
            subprocess.call(['python', 'delete.py'])

if __name__ == "__main__":
    main()
