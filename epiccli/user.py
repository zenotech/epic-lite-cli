import click
import requests
import os
import json

def create_user(username, email, password, project_config, project_name):
    """Creates a new user and generates a configuration file for them.

    This function sends a POST request to the /users endpoint of the EPIC API
    to create a new user in the Cognito User Pool. If the user is created
    successfully, it generates a JSON file named `{username}.json` containing
    the project configuration and credentials for the new user. This file can
    then be used by the new user to configure their own `epiccli`.

    This is an admin-only operation and requires an admin API token.

    Args:
        username (str): The username for the new user.
        email (str): The email address for the new user.
        password (str): The password for the new user.
        project_config (dict): The configuration dictionary for the admin's
            active project.
        project_name (str): The name of the admin's active project.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: Admin user not initialized. Please run 'epic init' with an admin project configuration.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    api_url = project_config['epic_api_url']
    payload = {"username": username, "password": password, "email": email}

    try:
        click.echo(f"Creating user '{username}' via API...")
        response = requests.post(f"{api_url}/users", headers=headers, json=payload)

        if response.status_code == 201:
            user_json = {
                "project_name": f"{project_name}",
                "username": username,
                "password": password,
                "UserPoolClientId": project_config['user_pool_client_id'],
                "UserPoolId": project_config['user_pool_id'],
                "DataBucketName": project_config['data_bucket_name'],
                "BatchJobQueueName": project_config['batch_job_queue_name'],
                "EpicApiUrl": project_config['epic_api_url']
            }

            output_filename = f"{username}.json"
            with open(output_filename, 'w') as f:
                json.dump(user_json, f, indent=4)

            click.echo(f"\nUser '{username}' created successfully.")
            click.echo(f"Configuration file '{output_filename}' has been generated.")
            click.echo(f"Use it to configure the EPIC CLI: epic config {output_filename}")

        elif response.status_code == 400:
            error_details = response.json()
            click.echo(f"Error: {error_details.get('error', 'Bad Request')}")
        elif response.status_code == 409:
            click.echo(f"User '{username}' may already exist.")
        else:
            response.raise_for_status()

    except requests.exceptions.RequestException as e:
        click.echo(f"Error creating user: {e}")


def delete_user(username, project_config):
    """Deletes a user from the Cognito User Pool.

    This function sends a DELETE request to the /users/{username} endpoint of
    the EPIC API to remove a user. It prompts for confirmation before
    proceeding.

    This is an admin-only operation and requires an admin API token.

    Args:
        username (str): The username of the user to be deleted.
        project_config (dict): The configuration dictionary for the admin's
            active project.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: Admin user not initialized. Please run 'epic init' with an admin project configuration.")
        return

    if not click.confirm(f"Are you sure you want to delete user '{username}'?"):
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        click.echo(f"Deleting user '{username}' via API...")
        response = requests.delete(f"{api_url}/users/{username}", headers=headers)

        if response.status_code == 204:
            click.echo(f"User '{username}' deleted successfully.")
        elif response.status_code == 404:
            click.echo(f"User '{username}' not found.")
        else:
            response.raise_for_status()

    except requests.exceptions.RequestException as e:
        click.echo(f"Error deleting user: {e}")
        if e.response:
            click.echo(f"Response: {e.response.text}")