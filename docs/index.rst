.. tv_transcript documentation master file, created by
   sphinx-quickstart on Sun Jun 26 22:56:02 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. module:: tv_transcript

TV Transcript's documentation
=============================

This module exposes several classes that simplifies the process of scraping,
parsing, serializing and querying a television show's transcript.

Uses `BeautifulSoup <https://www.crummy.com/software/BeautifulSoup/>`_ for parsing
and `requests <http://docs.python-requests.org/en/master/>`_ for HTTP.


Usage
#####

Start by subclassing the :class:`Show`, :class:`Season`, :class:`Episode` and
:class:`Line` classes, and implementing the parsing functions in each of them,
then overriding :meth:`Show.__init__` to take in the subclasses as default parameters.

The parsing functions take in a `BeautifulSoup` instance that represents the page
they are parsing. The example below shows the minimal amount of subclasses needed
to get started.

.. note::

   The parsing code in this section are simplified and do not actually work.
   See <https://github.com/ZhangYiJiang/mlp-visualization> for a real example of parsing code.

::

   from tv_transcript import Show, Episode, Line
   from collections import OrderedDicta
   import re

   class MLPEpisode(Episode):
       def _parse(self, page):
           title = page.select('#WikiaPageHeader h1')[0].string
           lines = []

           for dd in page.select('#mw-content-text > dl').children:
               speaker, line = self.get_text(dd).split(':', 1)

               # each dictionary in lines will be passed as **kwargs to the Line constructor
               lines.append({
                    'speaker': speaker,
                    'text': line
               })
           return title, lines

   class MLPLine(Line):
       def _parse_speaker(self, text, episode, number):
           return set(filter(None, re.split(r'\s*(?:,|\band\b)\s*', text)))

       def _parse_text(self, text, episode, number):
           return text

   class MyLittlePony(Show):
       def __init__(self, episode=MLPEpisode, line=MLPLine, **kwargs):
           super().__init__(episode=episode, line=line, **kwargs)

       def _parse(page, url):
           seasons = OrderedDict()
           for i, table in enumerate(page.select('#WikiaArticle table')):
               # key: season names, value: list of episode transcript URL
               seasons['Season ' + i] = [a.attr['href'] for a in table.find_all('a')]
           return seasons

To use these classes, ::

   # Loads and parses the MLP wiki transcript
   mlp = MyLittlePony(url='http://mlp.wikia.com/wiki/Episodes')

   # How many words were spoken in the second season?
   mlp.seasons[1].lines.wc

   # First 10 lines spoken by Twilight
   mlp.lines.by('Twilight Sparkle')[:10]

   # All episodes with Princesses in them
   princesses = {'Princess Celestia', 'Princess Luna', 'Princess Cadance'}
   filter(lambda ep: ep.lines.speakers() & princesses, mlp.episodes)

   # Characters who spoke in the episode 'The Gift of the Maud Pie'
   mlp.episode('The Gift of the Maud Pie').lines.speakers()

   # Every time Twilight said 'Pinkie'
   mlp.lines.filter(lambda l: 'Twilight Sparkle' in l.speaker and 'Pinkie' in l.text)

You'll notice the ``lines`` property that is common to the :class:`Show`,
:class:`Season` and :class:`Episode` objects. This property will always
contain a :class:`LineSet` object, which is a collection of :class:`Line`\ s
and exposes many useful methods for working with the transcript.

Extending Transcript Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Because the :class:`Episode`, :class:`Season` and :class:`Show` object will respect the
:class:`Line`, :class:`Episode` and :class:`Season` subclasses that are passed into
:class:`Show` constructor, this allows for the customization of the scraping and parsing
behavior by overriding the appropriate functions, as well as adding new properties
and methods to the classes to suit the TV show and the intended use of the transcript.

::

   class ScraperSeason(Season):
       def load(self, episodes):
           # Let us know which season is being scrapped
           print(self.name)
           super().load(episodes)

       def add_episode(self, episode):
           super().add_episode(episode)
           # Let us know which episode has just been scrapped
           print(episode.name)

   class PrincessCheckerLine(MLPLine):
       princesses = {'Princess Celestia', 'Princess Luna', 'Princess Cadance'}

       def is_princess(self):
           return self.speaker & self.princesses

   # This will now print out the season and episode names as they are being scrapped
   mlp = MyLittlePony(url='http://mlp.wikia.com/wiki/Episodes', season=ScraperSeason, line=PrincessCheckerLine)

   # How many lines are spoken by Princesses?
   len(show.lines.filter(lambda l: l.is_princess()))

Serialization and Deserialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Since scraping and parsing transcripts is time consuming, it is useful to persist the result
to disk, and read it off that when needed. This is also useful when the results are needed else
where. To do so, use :meth:`Show.serialize` to persist the transcript data to disk in JSON format.
To retrieve the saved data, use the *hydrate* parameter when instantiating the :class:`Show` class. ::

   mlp = MyLittlePony(url='http://mlp.wikia.com/wiki/Episodes')
   mlp.serialize()

   # Later on...
   mlp = MyLittlePony(hydrate=True)

By default the data is saved to a folder named the lowercase of the class name. To customize this,
override the :meth:`Show.storage_dir` method on the :class:`Show` class. ::

   class MyLittlePony(Show):
       def storage_dir(self):
           # Transcript data will always be saved to 'results' directory
           return 'results'

To serialize the transcript objects for your own use, you can use the provided
:class:`ModelEncoder` class, which is a subclass of :class:`json.JSONEncoder`
and implements the required :func:`default` method required.

.. note::

   The serialized JSON from the encoder is stable - the same data passed to it will result in the same
   output JSON string.

Iteration
^^^^^^^^^

Since :class:`Show`, :class:`Season`, :class:`Episode` and :class:`LineSet` classes
act as containers, they can be iterated, subscripted and counted like other
sequence types. ::

   # Count number of seasons
   len(mlp)

   # Number of lines in the episode 'Lesson Zero'
   len(mlp.episode('Lesson Zero'))

   # Print out every season 4 episode's name, number and first line
   for ep in mlp[3]:
       print(ep.number, ep.name, ep[0])

Class References
################

.. autoclass:: Show
   :members:
   :private-members:

   .. attribute:: seasons

      List of :class:`Season`\ s in this show

------------

.. autoclass:: LineSet
   :members:

------------

.. autoclass:: Season
   :members:

   .. attribute:: name

      The name of the season

   .. attribute:: order

      The season number, 1-indexed, so the first season is 1

   .. attribute:: show

      The :class:`Show` this season belongs to

   .. attribute:: episodes

      A list of :class:`Episode`\ s in this season

------------

.. autoclass:: Episode
   :members:
   :private-members:

   .. attribute:: name

      The name of the episode

   .. attribute:: number

      The show's number in the season, 1-indexed, so the first episode is 1, not 0

   .. attribute:: lines

      A :class:`LineSet` containing all lines in this episode

   .. attribute:: show

      The :class:`Show` this episode belongs to

   .. attribute:: season

      The :class:`Season` this episode belongs to

------------

.. autoclass:: Line
   :members:
   :private-members:
   
   .. attribute:: speaker

      The characters speaking the line, represented by a ``set`` of strings
      
   .. attribute:: text

      The text spoken in this line
      
   .. attribute:: number 

      The line's line number in the episode, 1-indexed
      
   .. attribute:: episode 

      The :class:`Episode` this line is from
