from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="warhammer40k_ai",
    version="0.1.0",
    author="Andrzej Gorski",
    author_email="nostrademous@hotmail.com",
    description="Warhammer 40k AI agent for testing AI strategies in playing Warhammer 40k",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SobolGaming/Warhammer40k_AI",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
    install_requires=[],
    entry_points={
        'console_scripts': [
            'warhammer40k_ai=warhammer40k_ai.UI.ModelUI:main',
        ],
    },
)