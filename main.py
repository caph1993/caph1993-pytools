from typing import List, TypedDict
from cp93pytools.audio import Sequence
from cp93pytools.methodtools import cached_property
#from cp93pytools.process import MyProcess, test
#from cp93pytools.easySqlite.store import test
from cp93pytools.easySqlite import SqliteTable, SqliteStore

#test()

# t = SqliteTable('', '')
# x= t.dicts(type=int)
# x


class MyDict(TypedDict):
    name: str
    age: int


def test_store():
    store = SqliteStore[str]('.test.db', 'the_table')
    print(store.db.table_names())
    print(len(store))
    store.wait_set('carlos', 'HELLO')
    print(store.dicts())
    with store.wait_token('carlos', 'adri') as token:
        print(f'I HAVE ACCESS! {token}')
        with store.ask_token('carlos') as access:
            assert access is None

    store.wait_set('carlos', 'HELLO2')
    store.wait_set('adri', 'BYE')
    store.wait_set('santiago', 'HMM')
    key = store.random_value('key', type=str)
    print(f'Deleting key={key}')
    store.delete(key, token)
    print('OK')


test_store()