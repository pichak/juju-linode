from setuptools import setup, find_packages

setup(name='juju-linode',
      version="0.1.0",
      classifiers=[
          'Intended Audience :: Developers',
          'Programming Language :: Python',
          'Operating System :: OS Independent'],
      author='Vahid Ashrafian',
      author_email='vahid.ashrafian@gmail.com',
      description="Linode integration with juju",
      long_description=open("README.rst").read(),
      url='https://github.com/pichak/juju-linode',
      license='BSD',
      packages=find_packages(),
      install_requires=["PyYAML", "requests", "jujuclient"],
      tests_require=["nose", "mock"],
      entry_points={
          "console_scripts": [
              'juju-linode = juju_linode.cli:main']},
      )
