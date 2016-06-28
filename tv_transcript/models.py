import requests
import time
import os
from hashlib import md5
from bs4 import BeautifulSoup
from .utils import remove_special, word_count, flatten
from operator import attrgetter
from typing import Any, Optional, Tuple, Mapping, Union, Sequence
from collections import OrderedDict

try:
    import simplejson as json
except ImportError:
    import json

Param = Mapping[str, Any]


class JSONSerializable:
    _hidden = []

    def to_json(self):
        o = self.__dict__
        for k in self._hidden:
            o.pop(k, None)
        return o


class PageParser:
    # Folder name of the cache
    cache = 'cache'
    parser = 'html.parser'
    ttl = 360

    @classmethod
    def get_file(cls, url):
        path = cls._cache_path(url)
        try:
            last_modified = os.path.getmtime(path)
            if (time.time() - last_modified) // 60 < cls.ttl:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                raise FileNotFoundError

        except FileNotFoundError:
            r = requests.get(url)

            try:
                os.makedirs(cls.cache, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(r.text)
            except OSError:
                pass

            return r.text

    @classmethod
    def _cache_path(cls, url):
        return os.path.join(cls.cache, md5(url.encode('utf-8')).hexdigest())

    @classmethod
    def get_page(cls, url):
        # TODO: use pickle for caching
        return BeautifulSoup(cls.get_file(url), cls.parser)

    @classmethod
    def clear_cache(cls, url):
        path = cls._cache_path(url)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    @classmethod
    def clear_all_cache(cls):
        for f in os.scandir(cls.cache):
            os.unlink(f.path)

    @staticmethod
    def get_text(tag):
        if tag.string:
            return tag.string.strip()
        return ''.join(tag.find_all(string=True))


class ModelEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, JSONSerializable):
            return o.to_json()
        if isinstance(o, (map, filter)):
            return list(o)
        if isinstance(o, set):
            return list(sorted(o))
        return super().default(o)


class IterableWrapper:
    _iterable = None

    def __iter__(self):
        return getattr(self, self._iterable).__iter__()

    def __getitem__(self, item):
        return getattr(self, self._iterable).__getitem__(item)

    def __len__(self):
        return getattr(self, self._iterable).__len__()

    def __contains__(self, item):
        return getattr(self, self._iterable).__contains__(item)

    def __bool__(self):
        return True


class LineSet(JSONSerializable, IterableWrapper):
    """
    Represents an ordered collection of :class:`Line`\ s. This is returned
    by the ``lines`` property of :class:`Show`, :class:`Season` and
    :class:`Episode` objects, which represents all of the lines contained by them.

    Subscript access and iteration of the :class:`Line` objects inside
    is allowed::

        # Counting number of lines in an episode
        len(mlp.episode('Lesson Zero').lines)

        # Iterating over first twenty lines in a season
        for line in mlp.seasons[3].lines[:20]:
            print(line.text)
    """
    _iterable = 'lines'

    def __init__(self, *lines):
        self.lines = []

        for l in lines:
            self.lines.extend(l)

    def to_json(self):
        return self.lines

    @property
    def wc(self):
        """The number of words in all lines inside this set of lines"""
        return sum(map(attrgetter('wc'), self.lines))

    def speakers(self) -> set:
        """
        Returns a ``set`` of strings representing all speaking characters involved. ::

            >>> mlp.episode('Maud Pie').lines.speakers()
            {'Hummingway', 'Rarity', 'Applejack', 'Rainbow Dash', 'Twilight Sparkle', 'Fluttershy', 'Winona',
             'Maud Pie', 'Pinkie Pie'}
        """
        speakers = set()
        for line in self.lines:
            speakers |= line.speaker
        return speakers

    def filter(self, predicate) -> 'LineSet':
        """
        Returns a new ``LineSet`` with only the lines that passes the *predicate*
        """
        return LineSet(filter(predicate, self.lines))

    def map(self, function) -> 'LineSet':
        """
        Returns a new ``LineSet`` with all of the lines transformed passing through the
        *function*. If a new ``LineSet`` is not needed, the global ``map()`` function
        should be used instead.
        """
        return LineSet(map(function, self.lines))

    def by(self, char) -> 'LineSet':
        """
        Returns a :class:`LineSet` of all lines spoken by a single character, or
        any one of a group of characters. ::

            # Lines spoken by Twilight
            episode.lines.by('Twilight Sparkle')

            # All lines spoken by any of the Princesses
            episode.lines.by({'Princess Celestia', 'Princess Celestia', 'Princess Cadance'})
        """
        if isinstance(char, str):
            char = {char}
        else:
            char = set(char)
        return self.filter(lambda l: char & l.speaker)

    def __repr__(self):
        return self.lines.__repr__()


class Line(JSONSerializable, IterableWrapper):
    """
    Class representing a single line in the transcript. Subclass this class and
    pass it in as the *line* parameter when instantiating a new :class:`Show` object
    so that the object uses the subclass
    """
    _hidden = ['episode', ]
    _iterable = 'text'

    def __init__(self, speaker, text, episode=None, number=None) -> None:
        self.episode = episode

        if number is None and episode:
            number = len(episode.lines) + 1

        self.number = number
        self.text = self._parse_text(text, episode, number)

        if isinstance(speaker, str):
            speaker = self._parse_speaker(speaker, episode, number)
        elif not isinstance(speaker, set):
            speaker = set(speaker)
        self.speaker = set(speaker)

    @property
    def wc(self) -> int:
        """Number of words in this line"""
        return word_count(self.text)

    def _parse_speaker(self, speaker, episode, number) -> set:
        """
        Implement this function in a subclass to extract the speaking character
        from
        """
        raise NotImplementedError

    def _parse_text(self, text, episode, number) -> str:
        raise NotImplementedError

    def __repr__(self):
        return ', '.join(self.speaker) + ': ' + self.text


class Episode(PageParser, JSONSerializable, IterableWrapper):
    """
    Class representing a single episode of a television show. Subclass this class
    and pass it as the *episode* parameter to the :class:`Show` class.
    """

    _hidden = ['show', 'season']
    _iterable = 'lines'

    def __init__(self, season=None, number=None, url=None, hydrate=None, show=None) -> None:
        self.lines = LineSet()
        self.season = season

        if show is None and season is not None:
            show = season.show
        self.show = show

        if hydrate:
            self.hydrate(hydrate)
            return

        if url:
            self.load(url)
        else:
            self.name = None

        if number is None:
            number = len(season.episodes) + 1
        self.number = number

    def _parse(self, page: BeautifulSoup, url: str):
        """
        Parse the provided episode transcript page into a 2- or 3-tuple with:

          1. The episode name or title
          2. A ``list`` of ``dict``, each of which will be passed to the :class:`Line` constructor
             defined in the :class:`Show` as ``**kwargs``. In other words each ``dict`` should have
             at least the keys *text* and *speaker*.
          3. Optionally any additional properties in a dictionary that need to be set on the Episode object

        Subclasses should override this function to enable parsing of episode transcripts.
        """
        raise NotImplementedError

    def load(self, url: str) -> 'Episode':
        """
        Scrapes and parses the episode transcript at *url* using the :meth:`_parse` method,
        then instantiate and store the resultant lines. Override this function to change
        the parsing or scraping behavior.
        """
        ret = self._parse(self.get_page(url), url)

        if len(ret) == 3:
            self.name, lines, kwargs = ret
            for k, v in kwargs.items():
                setattr(self, k, v)
        else:
            self.name, lines = ret

        self._add_lines(lines)
        return self

    def hydrate(self, data) -> 'Episode':
        for k, v in data.items():
            if k != 'lines':
                setattr(self, k, v)
            else:
                self._add_lines(v)

        return self

    def serialize(self) -> None:
        with open(self._filepath(), encoding='utf-8', mode='w') as f:
            json.dump(self, f, indent=4, cls=ModelEncoder)

    def _add_lines(self, lines) -> None:
        for line in lines:
            self.add_line(**line)

    def add_line(self, *args, **kwargs) -> Line:
        kwargs['episode'] = self
        line = self.show.create_line(*args, **kwargs)
        self.lines.lines.append(line)
        return line

    def _filepath(self) -> str:
        return os.path.join(self.season.storage_dir(), self._filename())

    def _filename(self, ext='json') -> str:
        """
        Override this function to change the file name used when persisting the episode
        transcript to disk.
        By default the name is ``<number> - <name>.json``, where ``number`` is the episode
        number and ``name`` is the episode name with special characters stripped out.
        """
        return str(self.number) + ' - ' + remove_special(self.name) + '.' + ext

    def __repr__(self):
        return self.name


class Season(IterableWrapper, JSONSerializable):
    """
    Class representing a single season of a television show. Acts as a collection of
    episodes and allows iteration over them. Subclass this class and pass it in as the
    *season* parameter to the :class:`Show` class if episode parsing or scraping
    behavior needs to be changed.
    """

    _iterable = 'episodes'

    _hidden = ['show', ]

    def __init__(self, order=None, name=None, show=None, urls=None, hydrate=False) -> None:
        self.show = show

        if order is None:
            order = len(show.seasons) + 1
        if name is None:
            name = order

        self.order = order
        self.name = name
        self.episodes = []

        if urls:
            self.load(urls)
        elif hydrate:
            self.hydrate()

    @property
    def lines(self) -> LineSet:
        """A :class:`LineSet` containing all of the lines in the season"""
        return LineSet(*map(attrgetter('lines'), self.episodes))

    def episode(self, name) -> Optional[Episode]:
        """Returns the first episode with *name*."""
        for episode in self.episodes:
            if episode.name == name:
                return episode

    def storage_dir(self) -> str:
        return os.path.join(self.show.storage_dir(), self.name)

    def load(self, episodes) -> 'Season':
        for url in episodes:
            episode = self.show.create_episode(season=self, url=url)
            self.add_episode(episode)
        self.sort()
        return self

    def serialize(self):
        if not os.path.exists(self.storage_dir()):
            os.mkdir(self.storage_dir())

        for episode in self.episodes:
            episode.serialize()

    def hydrate(self) -> 'Season':
        for file in os.scandir(self.storage_dir()):
            with open(file.path, encoding='utf-8') as f:
                data = json.load(f)
            self.add_episode(hydrate=data, season=self)

        self.sort()
        return self

    def sort(self, key='number'):
        self.episodes.sort(key=attrgetter(key))

    def add_episode(self, *args, **kwargs) -> Episode:
        """
        Creates a new episode and append it internally. All parameters are passed directly to the
        :class:`Episode` constructor.
        """
        episode = self.show.create_episode(*args, **kwargs)
        self.episodes.append(episode)
        return episode

    def __repr__(self):
        return self.name


class Show(PageParser, IterableWrapper, JSONSerializable):
    """
    Top level class representing a television show. Each Show object is an ordered
    collection of Seasons and is an iterable that iterates over Season objects.

    To load existing serialized data from disk, pass in *hydrate* as ``True``.

    To parse a show's transcript index page, subclass and implement the
    :meth:`._parse` method, then pass in the URL of the transcript index page
    as *url* when instantiating a new instance of the subclass.

    If *line*, *episode*, *season* are passed subclasses to :class:`Line`, :class:`Episode`
    and :class:`Season` respectively, they will be used in place of the default
    classes when they are instantiated. This is needed to enable parsing of transcripts
    as well as modifying parsing and scraping behavior, as well as adding additional
    methods and attributes to the transcript objects.

    The *parser* which BeautifulSoup uses when parsing the HTML. See
    `BeautifulSoup's documentation <https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser>`_
    for the parsers that are available.
    """

    ttl = 60 * 24
    _iterable = 'seasons'
    _hidden = ['create_episode', 'create_season', 'create_line', ]

    seasons = []

    def __init__(self, url=None, hydrate=False, season=None, episode=None, line=None, parser='html.parser') -> None:
        self.seasons = []

        self.create_episode = episode if episode else Episode
        self.create_season = season if season else Season
        self.create_line = line if line else Line
        PageParser.parser = parser

        if url:
            self.load(url)
        elif hydrate:
            self.hydrate()

    @property
    def episodes(self) -> Sequence[Episode]:
        """List of all :class:`Episode` in this show"""
        return flatten(s.episodes for s in self.seasons)

    @property
    def lines(self) -> LineSet:
        """A :class:`LineSet` containing all lines in the show"""
        return LineSet(*map(attrgetter('lines'), self.seasons))

    def episode(self, name: str) -> Optional[Episode]:
        """Get the first episode with *name*. """
        for episode in self.episodes:
            if episode.name == name:
                return episode

    def season(self, name) -> Optional[Season]:
        """Get the first season with *name*."""
        for season in self.seasons:
            if season.name == name:
                return season

    def serialize(self) -> None:
        """
        Persists the transcript data in this model to disk in JSON format. Saves the data to the
        directory given my :meth:`storage_dir`.
        """
        if not os.path.exists(self.storage_dir()):
            os.mkdir(self.storage_dir())

        with open(self.seasons_file(), encoding='utf-8', mode='w') as f:
            json.dump([s.name for s in self.seasons], f, indent=4)

        for season in self.seasons:
            season.serialize()

    def _parse(self, page: BeautifulSoup, url: str) -> Union[OrderedDict, Sequence[Tuple[str, Sequence[str]]]]:
        """
        Implement this method in a subclasses such that it returns an ``OrderedDict`` or a list of
        2-tuples of season name as key and a list of episode URLs as value. ::

            def _parse(page, url):
               seasons = OrderedDict()
               for i, table in enumerate(page.select('#WikiaArticle table')):
                   # key: season names, value: list of episode transcript URL
                   seasons['Season ' + i] = [a.attr['href'] for a in table.find_all('a')]
               return seasons
        """
        raise NotImplementedError

    def add_season(self, *args, **kwargs) -> Season:
        """
        Add a new season object to the current list of seasons. Passes all arguments
        to the constructor of the :class:`Season` class used by the show. There is usually
        no need to call this function directly since :meth:`load` or :meth:`hydrate`
        will call this automatically.
        """
        season = self.create_season(*args, **kwargs)
        self.seasons.append(season)
        return season

    def storage_dir(self) -> str:
        """
        Returns the directory to store the data when serializing the transcript.
        Override this method to change the location. Defaults to the lowercase of the class name.
        """
        return type(self).__name__.lower()

    def seasons_file(self) -> str:
        return os.path.join(self.storage_dir(), 'seasons.json')

    def load(self, url: str) -> 'Show':
        """
        Scrape and parse the transcript index page given by *url* to create seasons of
        episodes of the TV show. There is no need to call this function if *url*
        is already passed to the constructor.
        """
        seasons_page = self.get_page(url)
        seasons = self._parse(seasons_page, url)

        try:
            items = seasons.items()
        except AttributeError:
            items = seasons

        for name, episodes in items:
            self.add_season(name=name, show=self, urls=episodes)
        return self

    def hydrate(self) -> 'Show':
        """
        Loads persisted transcript data from disk. There is no need to call this function
        if the *hydrate* parameter is already passed to the constructor.
        """
        with open(self.seasons_file(), encoding='utf-8') as f:
            seasons = json.load(f)
        for season in seasons:
            self.add_season(name=season, show=self, hydrate=True)
        return self
