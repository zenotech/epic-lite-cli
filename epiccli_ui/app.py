
import webview
import threading
import json
import os
import requests
import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, redirect, url_for, session, jsonify, request

app = Flask(__name__)
app.secret_key = os.urandom(24)

# In-memory cache for S3 bucket stats
s3_bucket_stats_cache = {}

def get_config(project_name=None):
    """Reads the epic config file."""
    config_path = os.path.expanduser("~/.epic/config")
    if not os.path.exists(config_path):
        return None
    with open(config_path, 'r') as f:
        config = json.load(f)
    if project_name:
        return config.get(project_name)
    return config

def get_projects():
    """Reads the epic config file and returns a list of projects."""
    config = get_config()
    if not config:
        return []
    return list(config.keys())

@app.route('/')
def index():
    projects = get_projects()
    return render_template('index.html', projects=projects)

@app.route('/select_project/<project_name>')
def select_project(project_name):
    project_config = get_config(project_name)
    if not project_config:
        return redirect(url_for('index')) # Or an error page

    try:
        client = boto3.client('cognito-idp', region_name=project_config['region'])
        response = client.initiate_auth(
            ClientId=project_config['user_pool_client_id'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': project_config['username'],
                'PASSWORD': project_config['password']
            }
        )

        # Store all necessary info in the session
        session['api_token'] = response['AuthenticationResult']['IdToken']
        session['api_url'] = project_config.get('epic_api_url')
        session['project_id'] = project_name
        session['project_name'] = project_name
        session['username'] = project_config.get('username', 'user')

        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Login failed for project {project_name}: {e}")
        return redirect(url_for('index')) # Or a dedicated error page

@app.route('/dashboard')
def dashboard():
    project_name = session.get('project_name')
    if not project_name:
        return redirect(url_for('index'))

    # Ensure user is logged in
    if 'api_token' not in session:
        return redirect(url_for('index'))

    return render_template('dashboard.html', project_name=project_name, username=session.get('username'))

@app.route('/api/billing')
def api_billing():
    if 'api_token' not in session:
        return jsonify({"error": "Not logged in"}), 401

    api_url = session.get('api_url')
    project_id = session.get('project_id')
    headers = {'Authorization': f'Bearer {session["api_token"]}'}

    try:
        # Get project details to find the spend limit
        project_url = f'{api_url}/projects/{project_id}'
        project_resp = requests.get(project_url, headers=headers)
        project_resp.raise_for_status()
        project_data = project_resp.json()

        # Get billing data for current spend
        billing_url = f'{api_url}/billing/limits'
        billing_resp = requests.get(billing_url, headers=headers)
        billing_resp.raise_for_status()
        billing_data = billing_resp.json()

        return jsonify({
            "spend_limit": project_data.get("spend_limit", "N/A"),
            "current_spend": billing_data.get("monthly_spend", "N/A")
        })
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/jobs')
def api_jobs():
    if 'api_token' not in session:
        return jsonify({"error": "Not logged in"}), 401

    api_url = session.get('api_url')
    headers = {'Authorization': f'Bearer {session["api_token"]}'}
    url = f'{api_url}/job'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        jobs = response_data.get('results', [])

        return jsonify(jobs)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/cancel_job/<job_uuid>', methods=['POST'])
def api_cancel_job(job_uuid):
    if 'api_token' not in session:
        return jsonify({"error": "Not logged in"}), 401

    api_url = session.get('api_url')
    headers = {'Authorization': f'Bearer {session["api_token"]}'}
    url = f'{api_url}/job/{job_uuid}/cancel'
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return jsonify({"message": "Job cancellation requested"}), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/job/<job_uuid>/tail')
def api_job_tail(job_uuid):
    if 'api_token' not in session:
        return jsonify({"error": "Not logged in"}), 401

    api_url = session.get('api_url')
    headers = {'Authorization': f'Bearer {session["api_token"]}'}
    url = f'{api_url}/job/{job_uuid}/tail'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# S3 Helper
def get_s3_client():
    if 'api_token' not in session:
        raise Exception("Not logged in")

    api_url = session.get('api_url')
    headers = {'Authorization': f'Bearer {session["api_token"]}'}
    keys_url = f'{api_url}/data/session'

    try:
        response = requests.get(f"{api_url}/data/session", headers=headers)
        response.raise_for_status()
        keys = response.json()
        s3_client = boto3.client(
            's3',
            aws_access_key_id=keys['aws_access_key_id'],
            aws_secret_access_key=keys['aws_secret_access_key'],
            aws_session_token=keys['aws_session_token'],
            region_name=keys['aws_region']
        )
        return s3_client, keys['s3_location']
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get S3 credentials from API: {e}")
    except (ClientError, KeyError) as e:
        raise Exception(f"Failed to create S3 client: {e}")

# S3 API Endpoints
@app.route('/api/s3/rename-folder', methods=['POST'])
def api_s3_rename_folder():
    data = request.get_json()
    old_prefix = data.get('old_prefix')
    new_prefix = data.get('new_prefix')

    if not old_prefix or not new_prefix:
        return jsonify({"error": "Missing old_prefix or new_prefix"}), 400
    if not old_prefix.endswith('/'):
        old_prefix += '/'
    if not new_prefix.endswith('/'):
        new_prefix += '/'
    if old_prefix == new_prefix:
        return jsonify({"message": "Source and destination are the same."})

    try:
        s3_client, bucket_name = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')
        objects_to_delete = []

        for page in paginator.paginate(Bucket=bucket_name, Prefix=old_prefix):
            for obj in page.get('Contents', []):
                old_key = obj['Key']
                if old_key.startswith(old_prefix):
                    relative_key = old_key[len(old_prefix):]
                    new_key = f"{new_prefix}{relative_key}"
                    s3_client.copy_object(Bucket=bucket_name, CopySource={'Bucket': bucket_name, 'Key': old_key}, Key=new_key)
                    objects_to_delete.append({'Key': old_key})

        if objects_to_delete:
            # S3 delete_objects can handle up to 1000 keys at a time.
            for i in range(0, len(objects_to_delete), 1000):
                s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': objects_to_delete[i:i+1000]}
                )

        return jsonify({"message": f"Successfully renamed folder {old_prefix} to {new_prefix}"})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/copy-folder', methods=['POST'])
def api_s3_copy_folder():
    data = request.get_json()
    source_folder = data.get('source_folder')
    destination_folder = data.get('destination_folder')

    if not source_folder or not destination_folder:
        return jsonify({"error": "Missing source_folder or destination_folder"}), 400
    if not source_folder.endswith('/'):
        source_folder += '/'
    if not destination_folder.endswith('/'):
        destination_folder += '/'
    if source_folder == destination_folder:
        return jsonify({"message": "Source and destination are the same."})

    try:
        s3_client, bucket_name = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=bucket_name, Prefix=source_folder):
            for obj in page.get('Contents', []):
                old_key = obj['Key']
                if old_key.startswith(source_folder):
                    relative_key = old_key[len(source_folder):]
                    new_key = f"{destination_folder}{relative_key}"
                    s3_client.copy_object(Bucket=bucket_name, CopySource={'Bucket': bucket_name, 'Key': old_key}, Key=new_key)

        return jsonify({"message": f"Successfully copied folder {source_folder} to {destination_folder}"})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/list')
def api_s3_list():
    prefix = request.args.get('prefix', '')
    try:
        s3_client, bucket_name = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/')

        files = []
        folders = []

        for page in response_iterator:
            for common_prefix in page.get('CommonPrefixes', []):
                folders.append(common_prefix.get('Prefix'))
            for content in page.get('Contents', []):
                # Don't include the folder placeholder itself
                if content.get('Key') != prefix:
                    files.append({
                        'key': content.get('Key'),
                        'size': content.get('Size'),
                        'last_modified': content.get('LastModified').isoformat()
                    })

        return jsonify({'files': files, 'folders': folders})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/presigned-url/upload', methods=['POST'])
def api_s3_presigned_upload():
    data = request.get_json()
    key = data.get('key')
    if not key:
        return jsonify({"error": "Missing file key"}), 400

    try:
        s3_client, bucket_name = get_s3_client()
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=3600  # 1 hour
        )
        return jsonify({'url': url})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/presigned-url/download', methods=['POST'])
def api_s3_presigned_download():
    data = request.get_json()
    key = data.get('key')
    if not key:
        return jsonify({"error": "Missing file key"}), 400

    try:
        s3_client, bucket_name = get_s3_client()
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=3600  # 1 hour
        )
        return jsonify({'url': url})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/delete', methods=['POST'])
def api_s3_delete():
    data = request.get_json()
    key = data.get('key')
    if not key:
        return jsonify({"error": "Missing file key"}), 400

    try:
        s3_client, bucket_name = get_s3_client()
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        return jsonify({"message": f"Successfully deleted {key}"})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/rename', methods=['POST'])
def api_s3_rename():
    data = request.get_json()
    old_key = data.get('old_key')
    new_key = data.get('new_key')
    if not old_key or not new_key:
        return jsonify({"error": "Missing old_key or new_key"}), 400

    try:
        s3_client, bucket_name = get_s3_client()
        # Copy object
        s3_client.copy_object(Bucket=bucket_name, CopySource={'Bucket': bucket_name, 'Key': old_key}, Key=new_key)
        # Delete old object
        s3_client.delete_object(Bucket=bucket_name, Key=old_key)
        return jsonify({"message": f"Successfully renamed {old_key} to {new_key}"})
    except ClientError as e:
        # If the copy succeeded but delete failed, we should let the user know.
        return jsonify({"error": f"S3 Error during rename: {e.response['Error']['Message']}. The original file may still exist."}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred during rename: {e}"}), 500

@app.route('/api/s3/copy', methods=['POST'])
def api_s3_copy():
    data = request.get_json()
    source_key = data.get('source_key')
    destination_key = data.get('destination_key')
    if not source_key or not destination_key:
        return jsonify({"error": "Missing source_key or destination_key"}), 400

    try:
        s3_client, bucket_name = get_s3_client()
        s3_client.copy_object(Bucket=bucket_name, CopySource={'Bucket': bucket_name, 'Key': source_key}, Key=destination_key)
        return jsonify({"message": f"Successfully copied {source_key} to {destination_key}"})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/delete-folder', methods=['POST'])
def api_s3_delete_folder():
    data = request.get_json()
    prefix = data.get('prefix')
    if not prefix:
        return jsonify({"error": "Missing folder prefix"}), 400
    if not prefix.endswith('/'):
        prefix += '/'

    try:
        s3_client, bucket_name = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')
        objects_to_delete = []

        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    objects_to_delete.append({'Key': obj['Key']})

        if not objects_to_delete:
            return jsonify({"message": "Folder is already empty or does not exist."})

        # S3 delete_objects can handle up to 1000 keys at a time.
        for i in range(0, len(objects_to_delete), 1000):
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': objects_to_delete[i:i+1000]}
            )

        return jsonify({"message": f"Successfully deleted folder {prefix}"})
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/view/<path:key>')
def api_s3_view(key):
    try:
        s3_client, bucket_name = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        if key.endswith('.png'):
            content_type = 'image/png'
        else:
            content_type = 'application/octet-stream'  # safe for VTK.js
        print(content_type)
        return response['Body'].read(), 200, {'Content-Type': content_type}
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return jsonify({"error": "File not found"}), 404
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/api/s3/bucket-size')
def api_s3_bucket_size():
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({"error": "Project not in session"}), 400

    # Check cache first
    if project_id in s3_bucket_stats_cache:
        return jsonify(s3_bucket_stats_cache[project_id])

    try:
        s3_client, bucket_name = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')
        total_size = 0
        total_objects = 0
        for page in paginator.paginate(Bucket=bucket_name):
            contents = page.get('Contents', [])
            total_objects += len(contents)
            for content in contents:
                total_size += content.get('Size', 0)

        stats = {'total_size': total_size, 'total_objects': total_objects}
        s3_bucket_stats_cache[project_id] = stats
        return jsonify(stats)
    except ClientError as e:
        return jsonify({"error": f"S3 Error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=2395)
