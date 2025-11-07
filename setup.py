from setuptools import setup, find_packages

setup(
    name='queuectl',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'typer[all]',
        'psutil',
    ],
    entry_points={
        'console_scripts': [
            'queuectl = queuectl.main:app',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)