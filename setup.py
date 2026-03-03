from setuptools import setup, find_packages

from pathlib import Path
import re


def _read_version() -> str:
    version_path = Path(__file__).parent / "src" / "warhammer40k_ai" / "version.py"
    content = version_path.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', content, re.M)
    if not match:
        raise RuntimeError("APP_VERSION not found in version.py")
    return match.group(1)

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


ML_OPTIONAL_EXTRAS = [
    "torch>=2.2,<3.0",
    "torchrl>=0.6,<1.0",
    "torch-geometric>=2.6,<3.0",
    "ray[rllib]>=2.0,<3.0",
    "wandb>=0.16,<1.0",
]

setup(
    name="warhammer40k_ai",
    version=_read_version(),
    author="Andrzej Gorski",
    author_email="nostrademous@hotmail.com",
    description="Warhammer 40,000 rules engine and interactive UI",
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
    extras_require={
        "ml": ML_OPTIONAL_EXTRAS,
    },
    entry_points={
        'console_scripts': [
            'warhammer40k_ai=warhammer40k_ai.UI.ModelUI:main',
        ],
    },
)
