from requests import get
import socket
import configparser
Config = configparser.ConfigParser()
Config.read("project_config.ini")
Config.sections()

aws_access_key_id = \
    Config.get('aws_credentials', 'aws_access_key_id')

aws_secret_access_key = \
    Config.get('aws_credentials', 'aws_secret_access_key')

aws_session_token = \
    Config.get('aws_credentials', 'aws_session_token')

instance_identifier = \
    Config.get('new_instance_configuration', 'instance_identifier')


ip = get('https://api.ipify.org').text
print('My public IP address is:' + ip)


hostname = socket.gethostname()    
IPAddr = socket.gethostbyname(hostname)    
print("Your Computer Name is:" + hostname)    
print("Your Computer IP Address is:" + IPAddr)

print(f"{aws_access_key_id}\n{aws_secret_access_key}\n{aws_session_token}\n{instance_identifier}\n")