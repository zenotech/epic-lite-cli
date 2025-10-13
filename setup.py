from setuptools import setup, find_packages

with open('epiccli/requirements.txt') as f:
    required = f.read().splitlines()

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='epiccli-lite',
    version='0.1.1',
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
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)