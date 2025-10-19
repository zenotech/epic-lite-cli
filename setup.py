from setuptools import setup, find_packages

with open('epiccli/requirements.txt') as f:
    epic_cli_required = f.read().splitlines()

with open('epiccli_ui/requirements.txt') as f:
    epic_ui_required = f.read().splitlines()

required = list(set(epic_cli_required + epic_ui_required))

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='epiccli-lite',
    use_scm_version=True,
    author="Zenotech Ltd",
    author_email="support@zenotech.com",
    description="A CLI for the EPIC API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zenotech/epic-cli",
    packages=find_packages(),
    include_package_data=True,
    install_requires=required,
    entry_points={
        'console_scripts': [
            'epic=epiccli.main:cli',
            'epic-ui=epiccli.ui:main'
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
