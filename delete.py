import boto3
import subprocess
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de variables
STACK_NAME = os.getenv("STACK_NAME")
AWS_PROFILE = os.getenv("AWS_PROFILE")
AWS_REGION = os.getenv("AWS_REGION")

def delete_stack(cloudformation_client, stack_name, region_name):
    """Elimina un stack de CloudFormation."""
    print(f"Eliminando el stack {stack_name} en la región {region_name}...")
    try:
        cloudformation_client.delete_stack(StackName=stack_name)
        waiter = cloudformation_client.get_waiter('stack_delete_complete')
        waiter.wait(StackName=stack_name)
        print(f"El stack {stack_name} se ha eliminado exitosamente en la región {region_name}.")
        subprocess.call(['python', 'send_message.py', '--message', f"El stack {stack_name} se ha eliminado exitosamente en la región {region_name}."])
    except Exception as e:
        print(f"Error al eliminar el stack {stack_name} en la región {region_name}.")
        subprocess.call(['python', 'send_message.py', '--message', f"Error al eliminar el stack {stack_name} en la región {region_name}."])
        print("Revisando los eventos del stack para más detalles...\n")
        log_failed_events(cloudformation_client, stack_name)

def log_failed_events(cloudformation_client, stack_name):
    """Registra los eventos fallidos de un stack de CloudFormation."""
    events = cloudformation_client.describe_stack_events(StackName=stack_name)['StackEvents']
    failed_events = [event for event in events if 'FAILED' in event['ResourceStatus']]
    for event in failed_events:
        print(event['ResourceStatusReason'])

def execute_script(script_name):
    """Ejecuta un script de Python y retorna el resultado."""
    try:
        result = subprocess.check_call(['python', script_name])
        print(f"{script_name} se ejecutó correctamente.")
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar {script_name}: {e}")
        return e.returncode

if __name__ == "__main__":
    # Configuración de la sesión de boto3
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    cloudformation = session.client('cloudformation')

    # Ejecutar script de seed y eliminar el stack si tiene éxito
    if execute_script('delete_seed_sources.py') == 0:
        delete_stack(cloudformation, STACK_NAME, AWS_REGION)
    else:
        print("delete_seed_sources.py no se ejecutó correctamente. El stack no será eliminado.")
