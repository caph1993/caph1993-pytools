from typing import Union, Dict
from unidecode import unidecode
import re, json, time, requests, mimetypes
from mutagen.id3 import ID3NoHeaderError, Encoding
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TPE2, COMM, TCOM, TCON, TDRC, TRCK, USLT, APIC, TXXX
import lyricsgenius

def is_latin(s:str):
    is_latin = True
    try:
        s.encode('latin1')
    except:
        is_latin = False
    return is_latin


def latinize(s:str):
    '''(non-performant) unidecode for latin1 instead of ascii'''
    if is_latin(s):
        return s
    fixed = ''.join(c if is_latin(c) else unidecode(c) for c in s)
    assert is_latin(fixed)
    return fixed

genius_token = 'SOME TOKEN'
genius = lyricsgenius.Genius(genius_token)


class MyID3(ID3):
    
    _TAGS = dict(
        artist=TPE1,
        title=TIT2,
        album=TALB,
        track=TRCK,
        year=TDRC,
        comments=COMM,
        lyrics=USLT,
        picture=APIC,
        genius_id=TXXX,
        youtube_id=TXXX,
    )
    
    def __init__(self, fname:str):
        try:
            super().__init__(fname)
        except ID3NoHeaderError:
            super().__init__()
            self.save(fname)
        
        self.latinize_tags()
        self.make_lyrics_unique()
        self.make_picture_unique()
        # Remove garbage
        if str(self.get_tag('album', '')).lower() == 'youtube downloader audio':
            self.write_tag('album', text='')
    
    @classmethod
    def _TAG(cls, tag_name:str):
        tag_cls = cls._TAGS.get(tag_name, TXXX)
        tag_key = tag_cls.__name__
        
        if tag_cls is TXXX: # Custom tag
            kwargs = dict(
                encoding=Encoding.LATIN1,
                desc=tag_name,
                text='',
            )
            tag_key = f'TXXX:{tag_name}'
        elif tag_cls is APIC: # Picture tag
            kwargs = dict(
                encoding=Encoding.UTF8,
                data=bytes(),
                mime='image/jpeg',
                type=3,
                desc='Cover',
            )
        elif tag_cls is USLT: # Lyrics tag
            kwargs = dict(
                encoding=Encoding.LATIN1,
                text='',
                desc='',
                lang='XXX',
            )
        else: # Standard (text) tag
            kwargs = dict(
                encoding=Encoding.LATIN1,
                text='',
            )
        return tag_key, tag_cls, kwargs
    
    @classmethod
    def _LATIN_TAGS(cls):
        '''Tags that should be encoded using LATIN1'''
        zipped = [cls._TAG(key) for key in cls._TAGS]
        return [(k,cl,kw) for k,cl,kw in zipped if kw['encoding']==Encoding.LATIN1]
    
    def latinize_tags(self):
        for (k,v,kw) in self._LATIN_TAGS():
            value = self.get(str(v))
            if value and value.encoding != Encoding.LATIN1:
                value.text = latinize(value.text)
                value.encoding = Encoding.LATIN1
                self.save()
        return
        
    def make_lyrics_unique(self):
        '''
        Force at most one lyrics USLT tag
        Force also the default values
        '''
        uslt = [key for key in self.keys() if key.startswith('USLT')]
        lyrics = max([self[key].text for key in uslt]+[''], key=lambda s: len(str(s)))
        self.delall('USLT')
        self.write_tag('lyrics', text=lyrics)
        
    def make_picture_unique(self):
        '''
        Force at most one APIC tag
        Force also desc=''
        '''
        apic = [key for key in self.keys() if key.startswith('APIC')]
        if apic:
            best = self[max(apic, key=lambda key: len(str(self[key].data)))]
            self.delall('APIC')
            self.write_tag('picture', data=best.data, mime=best.mime, encoding=best.encoding)
    
    
    def write_tag(self, tag_name, **kwargs):
        tag_key, tag_cls, tag_kwargs = self._TAG(tag_name)
        kwargs = {**tag_kwargs, **kwargs}
        
        if kwargs['encoding'] == Encoding.LATIN1 and 'text' in kwargs:
            kwargs['text'] = latinize(kwargs['text'])
        
        self[tag_key] = tag_cls(**kwargs)
        self.save()
        
    def read_tag(self, tag_name):
        tag_key, _, _ = self._TAG(tag_name)
        return self[tag_key]
    
    def get_tag(self, tag_name, default=None):
        tag_key, _, _ = self._TAG(tag_name)
        return self.get(tag_key, default)
    
    def get_json(self, tag_name, default=None):
        tag_key, _, _ = self._TAG(tag_name)
        tag = self.get(tag_key, None)
        if tag:
            try:
                data = json.loads(str(tag))
            except:
                data = default
        else:
            data = default
        return data
    
    def __str__(self):
        title = str(self.read_tag('title'))
        artist = str(self.read_tag('artist'))
        tags = ['genius_json', 'lyrics', 'picture']
        plus = ''.join(f'+{tag}' for tag in tags if self.get_tag(tag))
        return f'"{title}" by {artist} [{plus}]'


def auto_lyrics(genius, id3, recent_days=30, sleep_seconds=5):
    last = id3.get_json('genius_timestamp')
    searched_recently = False
    days = 3600 * 24
    if isinstance(last, float):
        searched_recently = (time.time() < last + recent_days*days)
    
    data = id3.get_json('genius_json')
    if not data and not searched_recently:
        title = str(id3.read_tag('title'))
        artist = str(id3.read_tag('artist'))
        time.sleep(sleep_seconds)
        response = genius.search_song(title, artist) # (None if not found)
        id3.write_tag('genius_timestamp', text=json.dumps(time.time()))
        if response:
            id3.write_tag('genius_json', text=response.to_json())
            data = id3.get_json('genius_json', {})
            lyrics = data.get('lyrics', '')
            id3.write_tag('lyrics', text=lyrics)
    return


def auto_picture(id3, sleep_seconds=3):
    if not id3.get_tag('picture'):
        url = id3.get_json('genius_json', {}).get('song_art_image_url', '')
        mime, _ = mimetypes.guess_type(url)
        if url and mime:
            time.sleep(sleep_seconds)
            data = requests.get(url, stream=True).raw.data
            id3.write_tag('picture', data=data, mime=mime)
    return


import os

def print_enum(it):
    l = list(it)
    yield from ((print(f'{i}/{len(l)}') or x) for i,x in enumerate(l))
    print(f'({len(l)}/{len(l)})')

def del_all_pictures(id3s):
    for id3 in id3s:
        id3.delall('APIC')
        id3.save()
    return


xdir = '/home/carlos/Mega/Redmi 8/songs/Instrumental A/'
id3s = [MyID3(f'{xdir}/{xfile}') for xfile in sorted(os.listdir(xdir))]

for id3 in print_enum(id3s):
    print(id3)
    try:
        auto_lyrics(genius, id3)
        auto_picture(id3)
    except Exception as e:
        print(e)
    print(id3)

