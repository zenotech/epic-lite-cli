import click
import requests
import os
import json

def list_applications(project_config):
    """
    Lists available applications in the catalog.

    This command retrieves and displays a list of all HPC applications that
    can be run through the EPIC platform. The output includes the application's
    display name, a brief description, and the unique ``app_code`` used when
    submitting jobs.

    :param project_config: A dictionary containing the active project's configuration.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.get(f"{api_url}/catalog/applications", headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data.get('results'):
            click.echo("No applications found.")
            return

        click.echo("Available Applications:")
        for app in data['results']:
            product = app.get('product', {})
            versions = app.get('versions', [{}])
            click.echo(f"- {product.get('name')}:")
            click.echo(f"  Description: {product.get('description')}")
            click.echo(f"  App Code: {versions[0].get('app_code')}")

    except requests.exceptions.RequestException as e:
        click.echo(f"Error fetching applications: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")

def list_instances(project_config):
    """
    Lists available compute instance types in the catalog.

    This command retrieves and displays a list of the AWS EC2 instance types
    that are available for running jobs in the current deployment. The output
    includes the instance type name, the number of vCPUs, and the available
    memory in GB.

    :param project_config: A dictionary containing the active project's configuration.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.get(f"{api_url}/catalog/instances", headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data.get('instances'):
            click.echo("No instance types found.")
            return

        click.echo("Available Instance Types:")
        # Sort instances by name for consistent output
        sorted_instances = sorted(data['instances'], key=lambda i: i['instance_type'])
        for instance in sorted_instances:
            click.echo(
                f"- {instance['instance_type']}: "
                f"{instance['vcpus']} vCPUs, "
                f"{instance['memory_gb']:.2f} GB Memory"
            )

    except requests.exceptions.RequestException as e:
        click.echo(f"Error fetching instance types: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")
