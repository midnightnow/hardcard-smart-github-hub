from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="hardcard-github-hub",
    version="1.0.0",
    author="HardCard.AI",
    author_email="hub@hardcard.ai",
    description="Smart GitHub upload manager that prevents timeouts with intelligent chunking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hardcard-ai/smart-github-hub",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Version Control :: Git",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiohttp>=3.8.0",
        "aiofiles>=23.0.0",
        "PyGithub>=2.1.0",
        "GitPython>=3.1.0",
        "tqdm>=4.65.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "hardcard-hub=smart_upload_manager:main",
        ],
    },
)