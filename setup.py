from setuptools import setup

with open('README.rst', 'r') as readme_fd:
    long_description = readme_fd.read()

setup(
    name='dynamallow',
    version='0.0.1',

    description='Python ORM style interface to Amazon (AWS) DynamoDB using Marshmallow for Schema validation',
    long_description=long_description,
    author='Evan Borgstrom',
    author_email='evan@borgstrom.ca',
    url='https://github.com/borgstrom/dynamallow',
    license='Apache License Version 2.0',

    setup_requires=[
        'pytest-runner',
    ],
    install_requires=[
        'boto3>=1.3,<1.4',
        'marshmallow>=2.7.0,<2.8.0',
        'pytest>=2.9,<3.0',
        'six',
    ],
    packages=[
        'dynamallow',
    ],

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Topic :: Database',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries'
    ]
)
