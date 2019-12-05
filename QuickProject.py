from requests import get
import socket
import configparser
import boto3
import time
import pickle
import functools
import logging
import os

def retry(times, exceptions, sleep_secs):
    """
    Retry Decorator
    Retries the wrapped function/method `times` times if the exceptions listed
    in ``exceptions`` are thrown
    :param times: The number of times to repeat the wrapped function/method
    :type times: Int
    :param Exceptions: Lists of exceptions that trigger a retry attempt
    :type Exceptions: Tuple of Exceptions
    """
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(e)
                    attempt += 1
                    time.sleep(sleep_secs)
            return func(*args, **kwargs)
        return newfn
    return decorator

def get_config_parser(ini_filename):
    # ConfigParser to read config.ini
    Config = configparser.ConfigParser()
    Config.read(ini_filename)
    return Config

# Credentials
CredentialsConfig = get_config_parser('aws_credentials.ini')
aws_access_key_id = \
    CredentialsConfig.get('aws_credentials', 'aws_access_key_id')
aws_secret_access_key = \
    CredentialsConfig.get('aws_credentials', 'aws_secret_access_key')
aws_session_token = \
    CredentialsConfig.get('aws_credentials', 'aws_session_token')

# Project Config
ProjectConfig = get_config_parser('project_config.ini')
instance_identifier = ProjectConfig.get('new_instance_configuration', 'project_instance_identifier')
instance_ami = ProjectConfig.get('ec2_config', 'ami')
instance_type = ProjectConfig.get('ec2_config', 'instance_type') 
user_data_startup_script = ProjectConfig.get('ec2_config', 'userdata_startup_script')
instance_access_port = ProjectConfig.get('ec2_config', 'access_port')
VPC_CIDR_BLOCK = ProjectConfig.get('ec2_config', 'vpc_cidr_block')
PUBLIC_SUBNET_CIDR_BLOCK = ProjectConfig.get('ec2_config', 'subnet_cidr_block')
region = ProjectConfig.get('default', 'region')



def record_data(data_dict:dict, key, value):
    data_dict[key]=value
    pickle_data(data_dict)

def pickle_data(d:dict):
    with open('ids.pickle', 'wb') as handle:
        pickle.dump(d, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_data_from_pickle():
    try:
        with open('ids.pickle', 'rb') as handle:
            data_dict = pickle.load(handle)
            result = data_dict

    except:
        result = {}
    
    return result

# Loads data if already exists or starts 
data_dict = load_data_from_pickle()

@retry(5, (Exception),5)
def get_ec2_client(region):
    ec2 = boto3.client('ec2',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                region_name=region,
            )
    return ec2



@retry(20, (Exception),5)
def destroy_instance():
    

    ec2 = get_ec2_client(region)
    data_dict = load_data_from_pickle()

    time.sleep(3)

    try:
        ec2.terminate_instances(InstanceIds=[data_dict['ec2_instance']])
        time.sleep(10)
    except:
        pass

    try:
        ec2.delete_key_pair(KeyName=data_dict['keypair'])
    except:
        pass
    try:
        ec2.release_address(AllocationId=data_dict['elastic_ip'])
    except:
        pass
    try:
        ec2.detach_internet_gateway(VpcId=data_dict['vpc_id'],InternetGatewayId=data_dict['igw'])
    except:
        pass
    try:
        ec2.delete_internet_gateway(InternetGatewayId=data_dict['igw'])
        # ec2.delete_subnet(SubnetId=data_dict['subnet'])
        # ec2.delete_route_table(RouteTableId=data_dict['route_table_id'])
        # ec2.delete_security_group(GroupId=data_dict['security_group'])
    except:
        pass
    try:
        ec2.delete_vpc(VpcId = data_dict['vpc_id'])
    except:
        pass


def write_keypair_to_file(filename, key_material):

    if os.path.exists(filename):
        os.remove(filename)

    with open(filename,'w') as file:
        file.write(key_material)



@retry(5, (Exception),5)
def build_vpc():
    data_dict = load_data_from_pickle()
    try:
        vpc_data = ec2.create_vpc(CidrBlock=VPC_CIDR_BLOCK)
        VpcId = vpc_data['Vpc']['VpcId']
        ec2.create_tags(Resources=[VpcId], Tags=[{'Key':'Name', 'Value':instance_identifier+'_VPC'}])
        record_data(data_dict,'vpc_id', VpcId)
        result = VpcId
    except Exception as e:
        print(e)
        data_dict = load_data_from_pickle()
        result = data_dict['vpc_id']

    return result


@retry(5, (Exception),5)
def build_igw(VpcId):
    data_dict = load_data_from_pickle()
    try:
        igw_data = ec2.create_internet_gateway()
        igw_id = igw_data['InternetGateway']['InternetGatewayId']
        ec2.attach_internet_gateway(InternetGatewayId=igw_id,VpcId=VpcId)
        ec2.create_tags(Resources=[igw_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_IGW'}])
        data_dict['igw']=igw_id
        pickle_data(data_dict)
        result = igw_id
    except Exception as e:
        print(e)
        data_dict = load_data_from_pickle()
        result = data_dict['igw']

    return result


@retry(5, (Exception),5)
def build_keypair():
    key_pair_name = instance_identifier+'_KEY_PAIR'
    kp = ec2.create_key_pair(KeyName=key_pair_name)
    data_dict['keypair']=key_pair_name
    pickle_data(data_dict)

    # Write it to a local file
    privatekey=kp['KeyMaterial']
    filename=key_pair_name+'.pem'
    write_keypair_to_file(filename, privatekey)

    return key_pair_name


@retry(5, (Exception),5)
def build_subnet(VpcId):
    data_dict = load_data_from_pickle()
    try:
        subnet_data = ec2.create_subnet(VpcId=VpcId,
                                CidrBlock=PUBLIC_SUBNET_CIDR_BLOCK,
                                )
        subnet_id = subnet_data['Subnet']['SubnetId']
        ec2.create_tags(Resources=[subnet_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_Public_Subnet'}])

        data_dict['subnet']=subnet_id
        pickle_data(data_dict)

        result = subnet_id
    except Exception as e:
        print(e)
        
        result = data_dict['subnet']

    return result


@retry(5, (Exception),5)
def build_route_table(VpcId, subnet_id, igw_id):
    data_dict = load_data_from_pickle()
    try:
        route_table_data=ec2.create_route_table(VpcId=VpcId)
        route_tbl_id=route_table_data['RouteTable']['RouteTableId']
        ec2.create_tags(Resources=[route_tbl_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_RouteTable'}])
        ec2.create_route(RouteTableId=route_tbl_id,DestinationCidrBlock='0.0.0.0/0',GatewayId=igw_id)
        data_dict['route_table_id']=route_tbl_id
        pickle_data(data_dict)
        ec2.associate_route_table(RouteTableId=route_tbl_id,SubnetId=subnet_id)
        result =  route_tbl_id
    except Exception as e:
        print(e)
        result = data_dict['route_table_id']

    return result



@retry(5, (Exception),5)
def add_security_group_rule(security_group_id):
    ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
                'FromPort': 80,
                'ToPort': 80,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
                'FromPort': 443,
                'ToPort': 443,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
                'FromPort': int(instance_access_port),
                'ToPort': int(instance_access_port),
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        ])


@retry(5, (Exception),5)
def build_security_group(VpcId):
    data_dict = load_data_from_pickle()
    try:
        security_group_response_data = \
                ec2.create_security_group(GroupName=instance_identifier+'_SECURITY_GROUP',
                                            Description=instance_identifier+'_SECURITY_GROUP',
                                            VpcId=VpcId)

        security_group_id = security_group_response_data['GroupId']
        ec2.create_tags(Resources=[security_group_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_SECURITY_GROUP'}])
    except Exception as e:
        print(e)
        security_group_id = data_dict['security_group']

    try:
        add_security_group_rule(security_group_id)
        
    except Exception as e:
        print(e)
        pass

    data_dict['security_group']=security_group_id
    pickle_data(data_dict)
    return security_group_id


@retry(5, (Exception),5)
def build_ec2_instance(security_group_id, subnet_id, key_pair_name):
    try:
        instance_data = ec2.run_instances(ImageId=instance_ami,
                                    KeyName=key_pair_name,
                                    MinCount=1,
                                    MaxCount=1,
                                    SecurityGroupIds=[security_group_id],
                                    SubnetId=subnet_id,
                                    UserData=open(user_data_startup_script).read(),
                                    InstanceType=instance_type
                                    )

        instance_id = instance_data['Instances'][0]['InstanceId']
        ec2.create_tags(Resources=[instance_id], Tags=[{'Key':'Name', 'Value':instance_identifier+'_Instance'}])

        data_dict['ec2_instance']=instance_id
        pickle_data(data_dict)

        result = instance_id
    except:
        result = data_dict['ec2_instance']

    return result


@retry(5, (Exception),5)
def allocate_public_ip():
    data_dict = load_data_from_pickle()
    try:
        allocated_ip_data = ec2.allocate_address()
        allocation_id = allocated_ip_data['AllocationId']
        public_ip = allocated_ip_data['PublicIp']
        data_dict['public_ip']=public_ip
        data_dict['allocation_id']=allocation_id
        pickle_data(data_dict)
        result = (public_ip, allocation_id)
    except Exception as e:
        print(e)
        result = data_dict['public_ip'], data_dict['allocation_id']
 
    return result


@retry(5, (Exception),5)
def associate_public_ip(instance_id, allocation_id):
    
    print(f"""Your instance has to initialize before it can be assigned a public ip.""")
    while True:
        try:
            ec2.associate_address(InstanceId=instance_id, AllocationId=allocation_id)
            break
        except Exception as e:
            print(f"""Retrying in 20 seconds...""")
            time.sleep(20)


def print_successful_finalization_message(public_ip, instance_access_port, instance_identifier):
    try:
        project_name = ProjectConfig.get('new_instance_configuration', 'project_name')
        project_instance_identifier = ProjectConfig.get('new_instance_configuration', 'project_instance_identifier')
        message = ProjectConfig.get('success', 'message')
        address = f"{public_ip}:{instance_access_port}/"
        print(f"Your {project_name} - {project_instance_identifier} edition has been successfully initialized.")
        print(f"The web address is: \n\n{address}")
        print(message)
        print("\n-----------------------------------------------------")
    except:
        pass

if __name__=='__main__':

    ec2 = get_ec2_client(region)
    vpc_id = build_vpc()
    igw_id = build_igw(vpc_id)
    keypair_name = build_keypair()
    subnet_id = build_subnet(vpc_id)
    route_table_id = build_route_table(vpc_id, subnet_id, igw_id)
    security_group_id = build_security_group(vpc_id)
    ec2_instance_id = build_ec2_instance(security_group_id, subnet_id, keypair_name)
    public_ip, allocation_id = allocate_public_ip()
    associate_public_ip(ec2_instance_id, allocation_id)
    print_successful_finalization_message(public_ip, instance_access_port, ec2_instance_id)