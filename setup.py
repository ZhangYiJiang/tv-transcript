from setuptools import setup

setup(name='tv_transcript',
      version='0.0.2',
      description='Classes to help scrape, parse, process and serialize TV show transcripts on the internet',
      url='https://github.com/ZhangYiJiang/tv-transcript',
      author='Zhang Yi Jiang',
      keywords=['internet', 'television', 'transcript', 'scraping'],
      requires=[
          'bs4',
          'requests',
      ])
