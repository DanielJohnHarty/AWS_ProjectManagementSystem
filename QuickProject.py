from requests import get
import socket
import configparser
import boto3
import time
import pickle
import functools
import logging
import os
import sys


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
CredentialsConfig = get_config_parser("aws_credentials.ini")
aws_access_key_id = CredentialsConfig.get("aws_credentials", "aws_access_key_id")
aws_secret_access_key = CredentialsConfig.get(
    "aws_credentials", "aws_secret_access_key"
)
aws_session_token = CredentialsConfig.get("aws_credentials", "aws_session_token")


# Project Config
ProjectConfig = get_config_parser("project_config.ini")
instance_identifier = ProjectConfig.get(
    "new_instance_configuration", "project_instance_identifier"
)
instance_ami = ProjectConfig.get("ec2_config", "ami")
instance_type = ProjectConfig.get("ec2_config", "instance_type")
user_data_startup_script = ProjectConfig.get("ec2_config", "userdata_startup_script")
instance_access_port = ProjectConfig.get("ec2_config", "access_port")
VPC_CIDR_BLOCK = ProjectConfig.get("ec2_config", "vpc_cidr_block")
PUBLIC_SUBNET_CIDR_BLOCK = ProjectConfig.get("ec2_config", "subnet_cidr_block")
region = ProjectConfig.get("default", "region")


def pickle_data(d: dict):
    with open("ids.pickle", "wb") as handle:
        pickle.dump(d, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_data_from_pickle():
    try:
        with open("ids.pickle", "rb") as handle:
            data_dict = pickle.load(handle)
            result = data_dict

    except:
        result = {}

    return result


@retry(5, (Exception), 5)
def get_ec2_client(region):

    try:
        ec2 = boto3.client(
            "ec2",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region,
        )

    except Exception as e:
        print(f"Unable to create client object. Error:\n{e}\nExiting...")

    try:
        _ = ec2.describe_account_attributes()
    except Exception as e:
        print(f"Unable to validate client object. Error:\n{e}")

    return ec2


@retry(20, (Exception), 5)
def destroy_instance():

    ec2 = get_ec2_client(region)
    instance_data = load_data_from_pickle()

    try:
        ec2.terminate_instances(InstanceIds=[instance_data["ec2_instance"]])
        ec2_waiter = ec2.get_waiter("instance_terminated")
        ec2_waiter.wait(InstanceIds=[instance_data["ec2_instance"]])

        print("ec2 instance terminated...")


    except Exception as e:
        print("Unable to terminate ec2 instance:")
        print(e)
        print(
            "Due to the nature of the exception, \
            you should enter the AWS console to clean \
            up this OpenProject instance and network manually."
        )
        pass

    try:
        ec2.delete_key_pair(KeyName=instance_data["keypair"])
        print("Keypair deleted...")
    except Exception as e:
        print("Unable to delete keypair:")
        print(e)
        print(
            "Due to the nature of the exception, \
            you should enter the AWS console to clean \
            up this OpenProject instance and network manually."
        )
        pass

    try:
        ec2.release_address(AllocationId=instance_data["allocation_id"])
        print("public ip address released")

    except Exception as e:
        print("Unable to release public ip:")
        print(e)
        print(
            "Due to the nature of the exception, \
            you should enter the AWS console to clean \
            up this OpenProject instance and network manually."
        )
        pass

    try: 
        ec2.detach_internet_gateway(InternetGatewayId =instance_data['igw'], VpcId=instance_data['vpc_id'])
    except Exception as e:
        print(e)
        pass
    try:
        ec2.delete_internet_gateway(InternetGatewayId=instance_data["igw"])
    except Exception as e:
        print(e)
        pass
    try:
        ec2.delete_subnet(SubnetId =instance_data["subnet"])
    except Exception as e:
        print(e)
        pass
    try:
        ec2.delete_key_pair(KeyName =instance_data['keypair'])
    except Exception as e:
        print(e)
        pass
    try:
        ec2.delete_route_table(RouteTableId =instance_data["route_table_id"])
    except Exception as e:
        print(e)
        pass
    try:
        ec2.delete_security_group(GroupId =instance_data['security_group'])
    except Exception as e:
        print(e)
        pass
    try:
        attempts = 0
        while attempts < 3:
            try:
                ec2.delete_vpc(VpcId=instance_data["vpc_id"])
                break
            except Exception as e:
                attempts += 1
                print("Error deleting VPC: {}".format(e))
                print("{} attempts remain. Please wait:".format(4 - attempts))
                time.sleep(7)
                print("VPC deletion failed.")
                print(
                    "Due to the nature of the exception, \
                    you should enter the AWS console to clean \
                    up this OpenProject instance and network manually."
                )
                sys.exit()

        print("VPC deleted.")

    except Exception as e:
        print("Unable to delete VPC:")
        print(e)
        print(
            "Due to the nature of the exception, \
            you should enter the AWS console to clean \
            up this OpenProject instance and network manually."
        )


def write_keypair_to_file(filename, key_material):

    if os.path.exists(filename):
        os.remove(filename)

    with open(filename, "w") as file:
        file.write(key_material)


@retry(5, (Exception), 5)
def build_vpc(ec2_client):
    try:
        vpc_data = ec2_client.create_vpc(CidrBlock=VPC_CIDR_BLOCK)

        VpcId = vpc_data["Vpc"]["VpcId"]
        vpc_waiter = ec2_client.get_waiter("vpc_exists")
        vpc_waiter.wait(VpcIds=[VpcId])

        ec2_client.create_tags(
            Resources=[VpcId],
            Tags=[{"Key": "Name", "Value": instance_identifier + "_VPC"}],
        )

        result = VpcId

    except Exception as e:
        print(e)
        sys.exit()

    return result


@retry(5, (Exception), 5)
def build_igw(ec2_client, VpcId):

    try:
        igw_data = ec2_client.create_internet_gateway()
        igw_id = igw_data["InternetGateway"]["InternetGatewayId"]
        ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=VpcId)
        ec2_client.create_tags(
            Resources=[igw_id],
            Tags=[{"Key": "Name", "Value": instance_identifier + "_IGW"}],
        )

    except Exception as e:
        print(e)
        sys.exit()

    return igw_id


@retry(5, (Exception), 5)
def build_route_table(ec2_client, VpcId, subnet_id, igw_id):

    try:
        route_table_data = ec2_client.create_route_table(VpcId=VpcId)
        route_tbl_id = route_table_data["RouteTable"]["RouteTableId"]
        ec2_client.create_tags(
            Resources=[route_tbl_id],
            Tags=[{"Key": "Name", "Value": instance_identifier + "_RouteTable"}],
        )
        ec2_client.create_route(
            RouteTableId=route_tbl_id,
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=igw_id,
        )

        ec2_client.associate_route_table(RouteTableId=route_tbl_id, SubnetId=subnet_id)

    except Exception as e:
        print(e)
        sys.exit()

    return route_tbl_id


@retry(5, (Exception), 5)
def build_keypair(ec2_client):
    key_pair_name = instance_identifier + "_KEY_PAIR"

    try:
        kp = ec2_client.create_key_pair(KeyName=key_pair_name)

        # Write keypair to a local file
        privatekey = kp["KeyMaterial"]
        filename = key_pair_name + ".pem"
        write_keypair_to_file(filename, privatekey)

    except Exception as e:
        print(e)
        print("Looks like that keypair_name already exists. So you already have it.")
        pass

    return key_pair_name


@retry(5, (Exception), 5)
def build_subnet(ec2_client, VpcId):

    try:
        subnet_data = ec2_client.create_subnet(
            VpcId=VpcId, CidrBlock=PUBLIC_SUBNET_CIDR_BLOCK
        )
        subnet_id = subnet_data["Subnet"]["SubnetId"]
        ec2_client.create_tags(
            Resources=[subnet_id],
            Tags=[{"Key": "Name", "Value": instance_identifier + "_Public_Subnet"}],
        )

    except Exception as e:
        print(e)

    return subnet_id


@retry(5, (Exception), 5)
def add_security_group_rule(ec2_client, security_group_id):
    ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": int(instance_access_port),
                "ToPort": int(instance_access_port),
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }
        ],
    )


@retry(5, (Exception), 5)
def build_security_group(ec2_client, VpcId):

    try:
        security_group_response_data = ec2_client.create_security_group(
            GroupName=instance_identifier + "_SECURITY_GROUP",
            Description=instance_identifier + "_SECURITY_GROUP",
            VpcId=VpcId,
        )

        ec2_client.get_waiter("security_group_exists").wait()
        security_group_id = security_group_response_data["GroupId"]
        ec2_client.create_tags(
            Resources=[security_group_id],
            Tags=[{"Key": "Name", "Value": instance_identifier + "_SECURITY_GROUP"}],
        )
    except Exception as e:
        print("Couldn't create security group. Error:")
        print(e)
        pass

    try:
        add_security_group_rule(ec2_client, security_group_id)
        print("Added rule to security group")

    except Exception as e:
        print("Couldn't add rule to security group. Error:")
        print(e)
        pass

    return security_group_id


@retry(5, (Exception), 5)
def build_ec2_instance(ec2_client, security_group_id, subnet_id, key_pair_name):
    try:
        instance_data = ec2_client.run_instances(
            ImageId=instance_ami,
            KeyName=key_pair_name,
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=open(user_data_startup_script).read(),
            InstanceType=instance_type,
        )

        instance_id = instance_data["Instances"][0]["InstanceId"]
        ec2_client.create_tags(
            Resources=[instance_id],
            Tags=[{"Key": "Name", "Value": instance_identifier + "_Instance"}],
        )

    except Exception as e:
        print("Error creating EC2 instance. Error:")
        print(e)
        instance_id = e
        pass

    return instance_id


@retry(5, (Exception), 5)
def allocate_public_ip(ec2_client):

    try:
        allocated_ip_data = ec2_client.allocate_address()
        allocation_id = allocated_ip_data["AllocationId"]
        public_ip = allocated_ip_data["PublicIp"]
        result = (public_ip, allocation_id)
    except Exception as e:
        print("Unable to allocate public IP. Error:")
        print(e)
        result = "e", "e"

    return result


@retry(5, (Exception), 5)
def associate_public_ip(ec2_client, instance_id, allocation_id):

    print(f"""Just wait a few seconds before asociating a public IP please..""")
    while True:
        try:
            ec2_client.associate_address(
                InstanceId=instance_id, AllocationId=allocation_id
            )
            break
        except Exception as e:
            print(f"Error associating public IP. Error:\n{e}")
            print(f"""Retrying in 10 seconds...""")
            time.sleep(10)


def log_initialization_to_console(
    ec2_client, public_ip, instance_access_port, instance_identifier
):

    while True:
        current_status_details = ec2_client.describe_instance_status(
            InstanceIds=[instance_identifier]
        )
        current_status_name = current_status_details["InstanceStatuses"][0][
            "InstanceState"
        ]["Name"]
        if current_status_name == "running":
            break
        else:
            print("Instance initialisation state: {}".format(current_status_name))
            print("Please wait...")
            time.sleep(15)

    # Initialisation is complete. Share final message.
    try:
        project_name = ProjectConfig.get("new_instance_configuration", "project_name")
        project_instance_identifier = ProjectConfig.get(
            "new_instance_configuration", "project_instance_identifier"
        )
        message = ProjectConfig.get("success", "message")
        address = f"{public_ip}:{instance_access_port}/"
        print(message)
        print(f"Details: {project_name} - {project_instance_identifier}.")
        print(f"The web address is: \n\n{address}")
        print("\n-----------------------------------------------------")
    except Exception as e:
        print(e)


def launch_open_project_instance():
    launch_data = {}

    ec2_client = get_ec2_client(region)

    vpc_id = launch_data["vpc_id"] = build_vpc(ec2_client)
    igw_id = launch_data["igw"] = build_igw(ec2_client, vpc_id)
    keypair_name = launch_data["keypair"] = build_keypair(ec2_client)
    subnet_id = launch_data["subnet"] = build_subnet(ec2_client, vpc_id)
    route_table_id = launch_data["route_table_id"] = build_route_table(
        ec2_client, vpc_id, subnet_id, igw_id
    )
    security_group_id = launch_data["security_group"] = build_security_group(
        ec2_client, vpc_id
    )
    ec2_instance_id = launch_data["ec2_instance"] = build_ec2_instance(
        ec2_client, security_group_id, subnet_id, keypair_name
    )
    public_ip, allocation_id = (
        launch_data["public_ip"],
        launch_data["allocation_id"],
    ) = allocate_public_ip(ec2_client)
    associate_public_ip(ec2_client, ec2_instance_id, allocation_id)
    log_initialization_to_console(
        ec2_client, public_ip, instance_access_port, ec2_instance_id
    )

    pickle_data(launch_data)
    print("Launch data pickled.")


if __name__ == "__main__":

    try:
        if sys.argv[1].lower() == "destroy":
            print("Destroying instance...")
            destroy_instance()

    except:
        print("Launching instance...")
        launch_open_project_instance()
