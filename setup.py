# setup.py
from setuptools import setup, find_packages

setup(
    name="cerberus",
    version="0.1.1",
    author="necrqum",
    author_email="Pr0gr4mming12@gmail.com",
    description="Video-Downloader based on Selenium und yt_dlp",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/necrqum/cerberus", 
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "requests",
        "selenium",
        "tqdm",
        "yt-dlp",
        "beautifulsoup4",
        "browser-cookie3",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'cerberus = cerberus.downloader:main',
        ],
    },
)