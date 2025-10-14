import click
import requests
import os
import json

def get_project_details(project_name, project_config):
    """Fetches and displays details for a specific project.

    This function first lists all available projects to find the unique ID
    corresponding to the given project name. It then uses this ID to fetch
    the detailed project information, including the monthly spend limit, and
    prints it to the console.

    Args:
        project_name (str): The name of the project to get details for.
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    # First, list all projects to find the ID for the given name
    try:
        response = requests.get(f"{api_url}/projects", headers=headers)
        response.raise_for_status()
        projects = response.json()

        project_found = False
        for p in projects['results']:
            if p.get('project_id') == project_name:
                project_found = True
                break
        if not project_found:
            click.echo(f"Error: Project '{project_name}' not found on the server.")
            return

        # Then, get the specific project details
        response = requests.get(f"{api_url}/projects/{project_name}", headers=headers)
        response.raise_for_status()
        project = response.json()

        click.echo(f"Project ID: {project.get('project_id')}")
        click.echo(f"Description: {project.get('description')}")
        click.echo(f"Spend Limit: {project.get('spend_limit', 'Not set')}")

    except requests.exceptions.RequestException as e:
        click.echo(f"Error fetching project details: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")


def update_spend_limit(project_name, limit, project_config):
    """Updates the monthly spend limit for a project (admin only).

    This function first finds the ID of the project by its name, then sends a
    PATCH request to the /projects/{project_id} endpoint to update the
    `monthly_spend_limit`.

    Args:
        project_name (str): The name of the project to update.
        limit (int): The new monthly spend limit to set.
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    api_url = project_config['epic_api_url']

    # First, list all projects to find the ID for the given name
    try:
        response = requests.get(f"{api_url}/projects", headers=headers)
        response.raise_for_status()
        projects = response.json()

        project_found = False
        for p in projects['results']:
            if p.get('project_id') == project_name:
                project_found = True
                break

        if not project_found:
            click.echo(f"Error: Project '{project_name}' not found on the server.")
            return

        payload = {"spend_limit": limit}
        response = requests.patch(f"{api_url}/projects/{project_name}", headers=headers, json=payload)
        response.raise_for_status()

        click.echo(f"Successfully updated spend limit for '{project_name}' to ${limit}.")

    except requests.exceptions.RequestException as e:
        click.echo(f"Error updating spend limit: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")