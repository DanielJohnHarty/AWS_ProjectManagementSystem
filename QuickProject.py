from requests import get
import socket
import configparser
import boto3

# ConfigParser to read config.ini
Config = configparser.ConfigParser()
Config.read("project_config.ini")
Config.sections()

# All constants here
VPC_CIDR_BLOCK = '10.0.0.0/16'
PUBLIC_SUBNET_CIDR_BLOCK = '10.0.1.0/24'

# All variables here
aws_access_key_id = \
    Config.get('aws_credentials', 'aws_access_key_id')
aws_secret_access_key = \
    Config.get('aws_credentials', 'aws_secret_access_key')
aws_session_token = \
    Config.get('aws_credentials', 'aws_session_token')
instance_identifier = \
    Config.get('new_instance_configuration', 'instance_identifier')
my_public_ip = get('https://api.ipify.org').text
host_name = socket.gethostname()
my_network_ip = socket.gethostbyname(hostname)

def get_aws_client(aws_access_key_id, aws_secret_access_key, aws_session_token):
    