from setuptools import setup, find_packages

setup(
    name='gdrive_to_git',
    version='0.1',
    description='A tool for automating Google Drive versions to git commits.',
    author='Craig T. Nilson',
    author_email='craig.t.nilson@gmail.com',
    license='none',
    packages=find_packages(),
    install_requires=['google-api-python-client', 'google-auth-httplib2', 'google-auth-oauthlib', 'gitpython'],
    keywords=['git', 'google-drive', 'google-api']
)
