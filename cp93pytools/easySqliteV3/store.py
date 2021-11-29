from __future__ import annotations
from typing import List, Optional, Tuple
from contextlib import contextmanager
import json, time, random, logging
from .table import Record, SqliteTable, FilePath, Data


def create_deadline(timeout: Optional[float]):
    if timeout is None:
        return float('inf')
    return time.time() + timeout


class TimeoutError(Exception):
    message = 'Waiting for access token timed out'


class TokenError(Exception):
    message = 'Invalid or expired token'


class SqliteStore(SqliteTable):

    def __init__(self, file: FilePath, name: str):
        super().__init__(file, name)
        self.db.execute(f'''
        CREATE TABLE IF NOT EXISTS {self.name}(
            key text NOT NULL PRIMARY KEY,
            value text,
            lock_token double NOT NULL,
            locked_until double NOT NULL
        )
        ''')
        the_columns = {'key', 'value', 'lock_token', 'locked_until'}
        assert set(self.columns()) == the_columns, self.columns()
        return

    def __getitem__(self, key: str):
        d = super().where(key=key).get_dict('value')
        if not d:
            raise KeyError(key)
        return json.loads(d['value'] or 'null')

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def values(self):
        return [json.loads(s or 'null') for s in super().column('value')]

    def keys(self) -> List[str]:
        return [k for k in super().column('key')]

    def items(self) -> List[Tuple[str, Data]]:
        items = super().rows('key', 'value')
        return [(k, json.loads(v or 'null')) for k, v in items]

    def __set_assuming_token(self, key: str, value: Data):
        return super().where(key=key).update(value=json.dumps(value))

    def __del_assuming_token(self, key: str):
        return SqliteTable.delete(self.where(key=key))

    def _current_lock(self, key: str):
        return super().where(key=key).get_dict('lock_token', 'locked_until')

    def set(self, key: str, value: Data, token: float):
        '''
        Requires a token provided by the exclusive access context
        manager self.wait_token() or self.ask_token().
        '''
        with self.assert_token(key, token=token):
            self.__set_assuming_token(key, value)
        return

    def delete(self, key: str, token: float):
        '''
        Requires a token provided by the exclusive access context
        manager self.wait_token() or self.ask_token().
        '''
        with self.assert_token(key, token=token):
            self.__del_assuming_token(key)
        return

    def ask_del(self, key: str):
        with self.ask_token(key) as token:
            if not token:
                return False
            self.__del_assuming_token(key)
        return False

    def ask_set(self, key: str, value: Data):
        with self.ask_token(key) as token:
            if not token:
                return False
            self.__set_assuming_token(key, value)
        return False

    def wait_del(self, key: str, request_every: float = 0.02,
                 timeout: Optional[float] = 3):
        wait = self.wait_token(key, request_every=request_every,
                               timeout=timeout)
        with wait:
            self.__del_assuming_token(key)

    def wait_set(self, key: str, value: Data, request_every: float = 0.02,
                 timeout: Optional[float] = 3):
        wait = self.wait_token(key, request_every=request_every,
                               timeout=timeout)
        with wait as token:
            self.set(key, value, token)

    @contextmanager
    def ask_token(self, *keys: str, max_duration: float = 0.5):
        '''
        with table.ask_token('some_key') as token:
            if not token:
                # The resource is locked by other
            else:
                # The resource is mine
                table.set('some_key', some_value, token)
        '''
        assert keys, 'You must specify keys to be locked explicitely'
        token = random.random()
        try:
            gained_access = all([
                self._ask_access(key, token=token, max_duration=max_duration)
                for key in keys
            ])
            yield token if gained_access else None
        finally:
            for key in keys:
                self._unlock(key, token, max_duration)
        return

    @contextmanager
    def assert_token(self, *keys: str, token: float):
        assert keys, 'You must specify keys to be locked explicitely'
        max_duration = 0.5
        try:
            for key in keys:
                if not self._ask_access(key, token=token,
                                        max_duration=max_duration):
                    raise TokenError(key, token)
            yield
        finally:
            for key in keys:
                self._unlock(key, token, max_duration)
        return

    @contextmanager
    def wait_token(self, *keys: str, max_duration: float = 0.5,
                   request_every: float = 0.02, timeout: Optional[float] = 3,
                   _warn_del=True):
        '''
        # Wait at most {timeout} seconds to get exclusive access,
        # requesting every {request_every} seconds
        with table.wait_token('some_key') as token:
            current = table['some_key']
            ...
            # No one else can set some_key
            # during next {max_duration} seconds
            ...
            current = table.set('some_key', some_value, token)
        '''
        assert keys, 'You must specify keys to be locked explicitely'
        token = random.random()
        try:
            for key in keys:
                deadline = create_deadline(timeout)
                while not self._ask_access(key, token, max_duration):
                    if time.time() > deadline:
                        raise TimeoutError(timeout)
                    time.sleep(request_every)
            yield token
        finally:
            for key in keys:
                self._unlock(key, token, max_duration)
        return

    def _ask_access(self, key: str, token: float, max_duration: float):
        now = time.time()
        until = now + max_duration
        # Compete with other processes for an exclusive update
        cursor = self.db._execute(
            f'''
        UPDATE {self.name} SET
            lock_token=?,
            locked_until=?
        WHERE
            key=? AND (
                lock_token<0 OR
                lock_token=? OR
                locked_until<?
            )
        ''', [token, until, key, token, now])
        if cursor.rowcount > 0:  # Race winner
            return True
        # Maybe the key was not even present:
        return self.insert_or_ignore(
            key=key,
            lock_token=token,
            locked_until=until,
        )

    def _unlock(self, key: str, token: float, max_duration: float):
        d = self._current_lock(key)
        if not d:
            # Entry was deleted (and unlocked)
            return
        remaining = d['locked_until'] - time.time()
        if remaining < 0:
            ms = round(-remaining * 1000)
            logging.warning(
                f'Locked {repr(key)} during {ms}ms more than max_duration={max_duration}s'
            )
        if d['lock_token'] == token:
            super().where(key=key).update(lock_token=-1)
        return


def test():
    store = SqliteStore('.test.db', 'the_table')
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
    key = store.random_rows(1, 'key')[0][0]
    print(f'Deleting key={key}')
    store.delete(key, token)
    print('OK')
