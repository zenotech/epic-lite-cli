import click
import os
import json
import boto3
from botocore.exceptions import ClientError
import platform
from getpass import getpass
from .user import create_user as createUser, delete_user as deleteUser
from .project import get_project_details, update_spend_limit
from .billing import get_billing_info
from .data import get_data_keys
from .job import create_job, list_jobs, get_job, cancel_job, tail_job
from .catalog import list_applications as list_catalog_applications, list_instances as list_catalog_instances

CONFIG_DIR = os.path.expanduser("~/.epic")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config")

def get_config():
    """Loads the application configuration from the config file.

    The configuration is expected to be a JSON file located at ~/.epic/config.

    Returns:
        dict: The loaded configuration data. Returns an empty dictionary if
            the config file does not exist.
    """
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    """Saves the given configuration data to the config file.

    The configuration is stored as a JSON file at ~/.epic/config. This function
    will create the directory if it does not exist.

    Args:
        config (dict): The configuration data to save.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@click.group()
def cli():
    """A CLI for interacting with the EPIC API."""
    pass

@cli.group()
def config():
    """Commands for managing project configurations."""
    pass

@config.command(name="add")
@click.argument('user_json_file', type=click.Path(exists=True))
def add_config(user_json_file):
    """Adds or updates a project configuration from a user-specific JSON file.

    This command reads a JSON file typically generated for a new user, which
    contains all the necessary API endpoints and identifiers for a project.
    It saves this information into the main CLI config file (~/.epic/config)
    under the project's name.

    Args:
        user_json_file (str): The path to the user's JSON configuration file.
    """
    with open(user_json_file) as f:
        user_data = json.load(f)

    project_name = user_data.get("project_name")
    if not project_name:
        click.echo("Error: The JSON file must contain a 'project_name' field.")
        return

    config_data = get_config()

    project_config = {
        "user_pool_client_id": user_data.get("UserPoolClientId"),
        "user_pool_id": user_data.get("UserPoolId"),
        "data_bucket_name": user_data.get("DataBucketName"),
        "batch_job_queue_name": user_data.get("BatchJobQueueName"),
        "epic_api_url": user_data.get("EpicApiUrl"),
        "username": user_data.get("username"),
        "password": user_data.get("password"),
        "region": user_data.get("EpicApiUrl").split('.')[2] # Extract region from API URL
    }

    config_data[project_name] = project_config
    save_config(config_data)

    click.echo(f"Project '{project_name}' configured successfully.")

@config.command(name="list")
def list_config():
    """Lists all configured projects.

    Reads the main config file and prints the names of all projects that have
    been configured.
    """
    config = get_config()
    if not config:
        click.echo("No projects configured. Use 'epic config set' to add one.")
        return

    click.echo("Configured projects:")
    for project_name in config.keys():
        click.echo(f"- {project_name}")

@cli.command()
@click.argument('project_name')
def init(project_name):
    """Initializes a session for a configured project.

    This command authenticates the user with AWS Cognito using the stored
    username and password for the specified project. Upon successful
    authentication, it prints shell commands to set environment variables
    containing the API token and active project name.

    To apply these variables to your current session, you should wrap this
    command in `eval` (for bash/zsh) or pipe it to `Invoke-Expression`
    (for PowerShell).

    Example (bash/zsh):
        eval "$(epic init epic-project)"

    Example (PowerShell):
        epic init epic-project | Invoke-Expression

    Args:
        project_name (str): The name of the project to initialize.
    """
    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project '{project_name}' not found. Please configure it first using 'epic config'.")
        return

    project_config = config[project_name]
    username = project_config.get("username")
    password = project_config.get("password")

    if not password:
        password = getpass(f"Password for {username}: ")

    client = boto3.client('cognito-idp', region_name=project_config['region'])

    try:
        response = client.initiate_auth(
            ClientId=project_config['user_pool_client_id'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )

        id_token = response['AuthenticationResult']['IdToken']

        is_windows = platform.system() == 'Windows'

        click.echo("\n# Authentication successful!", err=True)
        if is_windows:
            click.echo("# To configure your current PowerShell session, pipe the output of this command to Invoke-Expression:", err=True)
            click.echo(f'# epic init {project_name} | Invoke-Expression', err=True)
            click.echo(f'$env:EPIC_API_TOKEN="{id_token}"')
            click.echo(f'$env:EPIC_ACTIVE_PROJECT="{project_name}"')
        else:
            click.echo("# To configure your current shell session, run the following command:", err=True)
            click.echo(f'# eval "$(epic init {project_name})"', err=True)
            click.echo(f"export EPIC_API_TOKEN='{id_token}'")
            click.echo(f"export EPIC_ACTIVE_PROJECT='{project_name}'")

        click.echo("\n# Note: These variables are only set for the current shell session.", err=True)
        click.echo("# You will need to run `epic init` again for new sessions.", err=True)

    except ClientError as e:
        if e.response['Error']['Code'] == 'NotAuthorizedException':
            click.echo("Authentication failed: Invalid username or password.")
        else:
            click.echo(f"An unexpected error occurred: {e}")

@cli.group()
def user():
    """User management commands (admin only)."""
    pass

@user.command(name="create")
@click.argument('username')
@click.argument('email')
@click.argument('password')
@click.option('--project', required=False, help='The project configuration to use for the admin user. Defaults to the active project.')
def create(username, email, password, project):
    """Creates a new user and generates a config file for them (admin only).

    This command calls the user creation endpoint of the API. Upon successful
    creation, it generates a new JSON configuration file named
    `{username}_config.json` containing the necessary details for the new
    user to configure their own CLI.

    Args:
        username (str): The username for the new user.
        email (str): The email address for the new user.
        password (str): The password for the new user.
        project (str, optional): The name of the project to use for the admin user. Defaults to the active project.
    """
    project_name = get_active_project(project)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    createUser(username, email, password, project_config, project_name)

@user.command(name="delete")
@click.argument('username')
@click.option('--project', required=False, help='The project configuration to use. Defaults to the active project.')
def delete(username, project):
    """Deletes a user (admin only).

    Args:
        username (str): The username of the user to delete.
        project (str, optional): The name of the project to use. Defaults to the active project.
    """
    project_name = get_active_project(project)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    deleteUser(username, project_config)


def get_active_project(project_name_arg=None):
    """Determines the active project name.

    This is a helper function that resolves the project name to use for a command.
    It prioritizes the project name passed as a direct argument. If that is not
    provided, it falls back to the `EPIC_ACTIVE_PROJECT` environment variable.

    Args:
        project_name_arg (str, optional): The project name from a command-line
            argument. Defaults to None.

    Returns:
        str or None: The resolved project name, or None if no project can be
            determined.
    """
    if project_name_arg:
        return project_name_arg

    active_project = os.environ.get("EPIC_ACTIVE_PROJECT")
    if not active_project:
        click.echo("Error: No project specified. Please provide a project name or set the EPIC_ACTIVE_PROJECT environment variable via 'epic init'.")
        return None
    return active_project

@cli.group()
def project():
    """Commands for managing projects."""
    pass

@project.command(name="get")
@click.argument('project_name', required=False)
def get_project(project_name):
    """Gets details for a project, including its monthly spend limit.

    Args:
        project_name (str, optional): The name of the project. Defaults to the
            active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    get_project_details(project_name, project_config)


@project.command(name="update-spend")
@click.argument('limit', type=int)
@click.argument('project_name', required=False)
def update_spend(limit, project_name):
    """Sets the monthly spend limit for a project (admin only).

    Args:
        limit (int): The new monthly spend limit.
        project_name (str, optional): The name of the project. Defaults to the active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    update_spend_limit(project_name, limit, project_config)

@cli.command()
@click.argument('project_name', required=False)
def billing(project_name):
    """Reports on the project's monthly spend to date.

    Args:
        project_name (str, optional): The name of the project. Defaults to the
            active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    get_billing_info(project_config)

@cli.command()
@click.argument('project_name', required=False)
@click.option('--awsconfig', is_flag=True, help='Output in AWS config file format.')
def keys(project_name, awsconfig):
    """Gets temporary data session keys as environment variables.

    This command fetches temporary AWS credentials and prints them as `export`
    commands, allowing for direct S3 access.

    Args:
        project_name (str, optional): The name of the project. Defaults to the
            active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    get_data_keys(project_config, project_name, awsconfig)

@cli.group()
def job():
    """Commands for managing jobs."""
    pass

@cli.group()
def catalog():
    """
    Commands for interacting with the EPIC catalog.

    The catalog provides information about available applications and compute
    resources (instance types) that can be used to run jobs.
    """
    pass

@catalog.command(name="list-applications")
@click.argument('project_name', required=False)
def list_applications_command(project_name):
    """
    Lists available applications in the catalog.

    This command retrieves and displays a list of all HPC applications that
    can be run through the EPIC platform. The output includes the application's
    display name, a brief description, and the unique ``app_code`` used when
    submitting jobs.

    :param project_name: The name of the project to use. Defaults to the active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    list_catalog_applications(project_config)

@catalog.command(name="list-instances")
@click.argument('project_name', required=False)
def list_instances_command(project_name):
    """
    Lists available compute instance types in the catalog.

    This command retrieves and displays a list of the AWS EC2 instance types
    that are available for running jobs in the current deployment. The output
    includes the instance type name, the number of vCPUs, and the available
    memory in GB.

    The list of available instances is configurable by the system administrator
    and is validated against the instances available in the AWS region where
    the EPIC API is deployed.

    :param project_name: The name of the project to use. Defaults to the active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    list_catalog_instances(project_config)

@job.command(name="create")
@click.argument('job_json_file', type=click.Path(exists=True))
@click.argument('project_name', required=False)
def create_job_command(job_json_file, project_name):
    """Creates a new job from a JSON file.

    Args:
        job_json_file (str): The file path to the JSON file containing the job
            definition.
        project_name (str, optional): The name of the project. Defaults to the
            active project.

    Example `job.json` files:

    .. code-block:: json

        {
            "name": "Test Job Array",
            "jobs": [{
                "name": "Test OpenFOAM Job",
                "spec": {
                    "app_code": "my-openfoamv8",
                    "tasks": [{"reference": "main-task", 
                                "partitions": 64, 
                                "runtime": 1, 
                                "task_distribution": "core",
                                "memory_gb": 16
                            }]
                },
                "input_data": {"path": "HPC_motorbike/Small/v8"},
                "app_options": {"base_command": ". /opt/openfoam8/etc/bashrc && ./Allrun"},
                "cluster": {"queue_code": "batch-single-node"}
            }]
        }

    .. code-block:: json

        {
            "name": "Test Job Array",
            "jobs": [{
                "name": "Test OpenFOAM Job",
                "spec": {
                    "app_code": "my-openfoam2212",
                    "tasks": [{"reference": "main-task", 
                                "partitions": 32, 
                                "runtime": 1, 
                                "task_distribution": "core",
                                "memory_gb": 16
                            }]
                },
                "input_data": {"path": "v2212/motorBike"},
                "app_options": {"base_command": "su sudofoam -c '. /usr/lib/openfoam/openfoam2212/etc/bashrc && ls -lta && ./Allclean && ./Allrun'"},
                "cluster": {"queue_code": "batch-single-node"}
            }]
        }    
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    create_job(job_json_file, project_config)

@job.command(name="list")
@click.argument('project_name', required=False)
def list_jobs_command(project_name):
    """Lists all current jobs and their status.

    Args:
        project_name (str, optional): The name of the project. Defaults to the
            active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    list_jobs(project_config)

@job.command(name="get")
@click.argument('job_id')
@click.argument('project_name', required=False)
def get_job_command(job_id, project_name):
    """Gets detailed information about a specific job.

    Args:
        job_id (int): The unique identifier for the job.
        project_name (str, optional): The name of the project. Defaults to the active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    get_job(job_id, project_config)

@job.command(name="cancel")
@click.argument('job_id')
@click.argument('project_name', required=False)
def cancel_job_command(job_id, project_name):
    """Cancels a specific job.

    Args:
        job_id (int): The unique identifier for the job to be cancelled.
        project_name (str, optional): The name of the project. Defaults to the active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    cancel_job(job_id, project_config)

@job.command(name="tail")
@click.argument('job_id')
@click.argument('project_name', required=False)
def tail_job_command(job_id, project_name):
    """Tails the logs of a specific job.

    Args:
        job_id (int): The unique identifier for the job.
        project_name (str, optional): The name of the project. Defaults to the active project.
    """
    project_name = get_active_project(project_name)
    if not project_name:
        return

    config = get_config()
    if project_name not in config:
        click.echo(f"Error: Project configuration '{project_name}' not found. Please configure it first using 'epic config'.")
        return
    project_config = config[project_name]
    tail_job(job_id, project_config)

if __name__ == '__main__':
    cli()