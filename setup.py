from setuptools import setup, find_packages

setup(
    name="trading-system",                  # Must be unique on PyPI
    version="0.1.0",
    description="Modular trading system ",
    author="Giacomo Telloli",
    author_email="tell.giacomo@gmail.com",
    url="https://github.com/giacomotelloli/TradingSystem",
    packages=find_packages(),               # Finds `trading_system/`
    install_requires=[
        "alpaca-trade-api==1.6.0",
        "python-dotenv==1.0.1",
        "PyYAML==6.0.1",
        "pyfiglet==1.0.2",
        "colorama==0.4.6"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
