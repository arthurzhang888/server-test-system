from setuptools import setup, find_packages

setup(
    name="server-test-system",
    version="0.1.0",
    description="Hardware testing system for production servers",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "click>=8.0.0",
        "rich>=13.0.0",
        "psutil>=5.9.0",
        "jinja2>=3.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
        ],
    },
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "server-test=main:cli",
        ],
    },
)
