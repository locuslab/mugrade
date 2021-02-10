from setuptools import setup, find_packages

setup(
	name="mugrade",
	version="1.0",
	author="Zico Kolter",
	author_email="zkolter@cs.cmu.edu",
	packages=find_packages(),
	description="Interface library for minimalist autograding site",
	python_requires=">=3.5",
	url="http://github.com/locuslab/mugrade",
	install_requires=["numpy >= 1.15"],
	setup_requires=["numpy >= 1.15"]
)

