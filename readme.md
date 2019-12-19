# Launch an AWS Hosted OpenProject Instance

This is a Python script (tested using 3.7) which launches an AWS EC2 linux instance, hosting the open source project management platform [Open Project](https://www.openproject.org).

The OpenProject instance is running inside a Docker container which is exposing port 80.



To use this script:

1. Clone this repository on your local machine with the command:

    ```git clone https://github.com/DanielJohnHarty/AWS_ProjectManagementSystem.git```

    ... and navigate to the locally cloned repository using a CLI (command line interface like bash or powershell).

2. Create a new python virtual environment, activate it and install the project requirements using the command:

    ```pip install -r requirements.txt```

3. Create an **aws_credentials.ini** file in the same folder, with the same format and with the fields as the **aws_default_credentials.ini**. Add your AWS credentials to it.

4. Create a **project_config.ini** file in the same folder and with the same format and fields as the **default_config.ini file**. Add a ***project_name*** and a ***project_instance_identifier*** for you project. *Additional fields in this file can be adjusted but changing them could lead to unexpected behaviour. Only modify them if you know what you're doing*. 

5. To launch your OpenProject instance, from the directory of your cloned repository, use the command:

    ```python QuickProject.py```

    You'll see some updates on the creation process on the command line, including the public IP where the instance is hosted.

    **When the script ends and you return to the cursor of your CLI, that means that all AWS instructions have been sent. You will have a period of 5-10 minutes to wait until you're able to visit the web address displayed as all software needs to be installed which takes some time.**
    

    > All of the details of the installation are stored in a local file called ***ids.pickle***. This contains no confidential info and is only used to facilitate the destroy_instance in the future, where **every aspect of the instance, infrasructure and data are fully destroyed, automatically**.

6. To destroy your instance, its infrastructure and all its data, use the command line again from the same directory:
    ```python QuickProject.py destroy```

**All of the actions taken by the QuickProject.py script are visible and can be modified from within the AWS console if necessary.**

## A note on security
The EC2 instance accepts requests on port 80 from anywhere, like a regular website might. The OpenProject application has a full suite of user administration tools meaning you can restrict access to your OpenProject by creating and managing users from the admin page of OpenProject. 

If you'd like to further increase security and limit who can access your *EC2 instance*, go to the AWS console and review the 'Inbound' rules of the security group related to your instance. *A secure way to control who can access your instance is, for each collaborator, to **add an inbound rule which allows HTTP requests on port 80 only from the public IP addresses of each of your collaborators.***

This is a choice you have but the default OpenProject admin tools would be enough for most personal use cases which don't include highly confidential infromation like credit card details.