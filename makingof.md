# In what contxt might you use this script?

If you're in a meeting with a new customer, friends, band members or your family and you have a complex project to carry out, you can quickly and easily create a private, secure and free project which everyone can access with the just a web browser. Upload photos, comment tasks, change dates - anything is possible.

When you're done and your project is over, you can be sure that deleting your project will delete all your data. There will be no ads, no spam email, nothing. When you decide it's over, one command and it's over. A rare thing in this digital age. 

## The casic functions of QuickProject are

1. new_instance ()-> A new instance means a new EC2 instance, with it's own public web address and possibility to customize, administer and add projects to
2. close_instance (instance) -> Destroy an instance, all it's projects and all it's data. After this, you can be sure that google won't be training any AI with your kids' pictures.

## new_instance

The create_new_instance function will do several things: 
1. Firstly, it will take you AWS details and connect with your AWS profile
2. Then it creates a custom vpc with the name and custom CIDR block you specify
3. Next a public subnet which is part of your VPC is created to host your instance
4. A security group for your instance is created which is open to all http and https requests plus ssh from the QuickProject Python script's device
5. An appropriate EC2 instance (4gb memory minimum) is created in the VPC and on the subnet created in steps 2 and 3. A public IP is assigned and the startup script is ran. The security group from step 4 is assigned and the startup script is run. Within a few minutes, the EC2 instance is up and running, with a docker container exposed on port 8080 running a clean installation of OpenProject. The full web address of the OpenProject server and the instance_id is returned to the caller. The web address to access the server, the instance_id to pass to the close_instance function to delete it.

## close_instance

1. The function is called with the instance_id as a parameter. The instance_id is actually the VPC id of the AWS infrastructure created especially for the OpenProject server. The VPC is deleted with out saving any data or backups.



