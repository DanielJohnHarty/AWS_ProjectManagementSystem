from requests import get
import socket
import configparser
import boto3
import time

# ConfigParser to read config.ini
Config = configparser.ConfigParser()
Config.read("project_config.ini")
Config.sections()

# All constants here
VPC_CIDR_BLOCK = Config.get('ec2_config', 'vpc_cidr_block')
PUBLIC_SUBNET_CIDR_BLOCK = Config.get('ec2_config', 'subnet_cidr_block')

# All variables here
aws_access_key_id = \
    Config.get('aws_credentials', 'aws_access_key_id')
aws_secret_access_key = \
    Config.get('aws_credentials', 'aws_secret_access_key')
aws_session_token = \
    Config.get('aws_credentials', 'aws_session_token')
instance_identifier = \
    Config.get('new_instance_configuration', 'project_instance_identifier')

# AMI
instance_ami = Config.get('ec2_config', 'ami')
instance_type = Config.get('ec2_config', 'instance_type') 

# IP and regions
region=Config.get('default', 'region')
my_public_ip = get('https://api.ipify.org').text
host_name = socket.gethostname()
my_network_ip = socket.gethostbyname(host_name)

# Read startup script to pass as user data

user_data = ''

with open(r"startup_scipt",'r') as file:
    for line in file:
        user_data += line


# Create client using credentials in ini
ec2 = boto3.client('ec2',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region,
        )

# Create VPC and tag it
vpc_data = ec2.create_vpc(CidrBlock=VPC_CIDR_BLOCK)
VpcId = vpc_data['Vpc']['VpcId']
ec2.create_tags(Resources=[VpcId], Tags=[{'Key':'Name', 'Value':instance_identifier+'_VPC'}])

# Create KeyPair
kp = ec2.create_key_pair(KeyName=instance_identifier+'_KEY_PAIR')
ec2.create_tags(Resources=[VpcId], Tags=[{'Key':'Name', 'Value':instance_identifier+'_VPC'}])

# Write it to a local file
with open(instance_identifier+'_KEY_PAIR.pem','w') as file:
    file.write(kp['KeyMaterial'])


#Create subnet and tag it
subnet_data = ec2.create_subnet(VpcId=VpcId,
                           CidrBlock=PUBLIC_SUBNET_CIDR_BLOCK,
                           )
subnet_id = subnet_data['Subnet']['SubnetId']
ec2.create_tags(Resources=[subnet_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_Public_Subnet'}])


# Create an internet gateway and associate it with the vpc
igw_data = ec2.create_internet_gateway()
igw_id = igw_data['InternetGateway']['InternetGatewayId']
ec2.attach_internet_gateway(InternetGatewayId=igw_id,VpcId=VpcId) # attache to VPC
ec2.create_tags(Resources=[igw_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_IGW'}]) # Tag it

# Create a security group for the instance
security_group_response_data = \
        ec2.create_security_group(GroupName=instance_identifier+'_SECURITY_GROUP',
                                    Description=instance_identifier+'_SECURITY_GROUP',
                                    VpcId=VpcId)
security_group_id = security_group_response_data['GroupId']
ec2.create_tags(Resources=[security_group_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_SECURITY_GROUP'}])
data = ec2.authorize_security_group_ingress(
    GroupId=security_group_id,
    IpPermissions=[
        {'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ])



instance_data = ec2.run_instances(ImageId=instance_ami,
                             KeyName=kp['KeyName'],
                             MinCount=1,
                             MaxCount=1,
                             SecurityGroupIds=[security_group_id],
                             SubnetId=subnet_id,
                             UserData=user_data,
                             InstanceType=instance_type
                             )

instance_id = instance_data['Instances'][0]['InstanceId']
ec2.create_tags(Resources=[instance_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_Instance'}]) # Tag it
allocated_ip_data = public_ip=ec2.allocate_address()

allocation_id = allocated_ip_data['AllocationId']
public_ip = allocated_ip_data['PublicIp']

while True:
    try:
        public_ip_data = ec2.associate_address(InstanceId=instance_id, AllocationId=allocation_id)
        break
    except Exception as e:
        print(e)
        time.sleep(30)

print(f"""Your OpenProject - {instance_identifier} edition will be online at http://{public_ip} in around 5 minutes.
          An administrator has been created automatically with username and password of 'admin'.
          Please make sure to update your admin password and invite your friends and family from
          the user interface. Good luck with your project!""")