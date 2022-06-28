import setuptools

setuptools.setup(
    name="gremlin",
    version="0.1",
    description="a microservice test tool",
    long_description="a microservice test tool",
    long_description_content_type="text",
    license="Apache License Version 2.0",

    author="YuSitong",
    author_email="yusitong1999@foxmail.com",

    packages=setuptools.find_packages(),
    include_package_data=True,
    platforms="any",
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Natural Language :: Chinese (Simplified)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.9.10',
    ],
    install_requires=[
        'certifi==2022.6.15',
        'charset-normalizer==2.0.12',
        'elastic-transport==8.1.2',
        'elasticsearch==1.7.0',
        'idna==3.3',
        'isodate==0.6.1',
        'networkx==2.8.4',
        'requests==2.28.0',
        'six==1.16.0',
        'urllib3==1.26.9',
    ],
)
