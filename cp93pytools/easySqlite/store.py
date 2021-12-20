from __future__ import annotations
from typing import Any, Generic, List, Optional, Tuple, TypeVar, cast
from typing_extensions import Type, TypedDict, overload

from contextlib import contextmanager
import json, time, random, logging
from .table import SqliteTable, FilePath


class StoreRecord(TypedDict):
    key: str
    value: Optional[str]
    lock_token: float
    locked_until: float


def create_deadline(timeout: Optional[float]):
    if timeout is None:
        return float('inf')
    return time.time() + timeout


class TimeoutError(Exception):
    message = 'Waiting for access token timed out'


class TokenError(Exception):
    message = 'Invalid or expired token'


Value = TypeVar('Value')
Data = TypeVar('Data')


class SqliteStore(Generic[Value], SqliteTable):

    def __init__(self, file: FilePath, name: str):
        self.table.__init__(file, name)
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

    @property
    def table(self):
        return cast(SqliteTable, super())

    def __getitem__(self, key: str):
        d = self.table.where(key=key).get_dict(
            'value',
            type=StoreRecord,
        )
        d = cast(Optional[StoreRecord], d)
        if not d or not d['value']:
            raise KeyError(key)
        value = json.loads(d['value'])
        return cast(Value, value)

    @overload
    def get(self, key: str) -> Optional[Value]:
        ...

    @overload
    def get(self, key: str, default: Value = None) -> Optional[Value]:
        ...

    def get(self, key: str, default=None):
        try:
            value = self[key]
        except KeyError:
            value = default
        return value

    def getT(self, key: str, default=None, type: Type = Any):
        try:
            value = self[key]
        except KeyError:
            value = default
        return cast(type, value)

    def values(self):
        col = self.table.where_sql(
            'value<>?',
            None,
        ).column('value', type=str)
        values = [json.loads(s) for s in col]
        return cast(List[Value], values)

    def keys(self):
        return self.table.column('value', type=str)

    def items(self):
        encoded = self.table.rows(
            'key',
            'value',
            type=Tuple[str, Optional[str]],
        )
        items = [(k, json.loads(v or 'null')) for k, v in encoded]
        items = cast(List[Tuple[str, Value]], items)
        return items

    def __set_assuming_token(self, key: str, value: Value):
        return self.table.where(key=key).update(value=json.dumps(value))

    def __del_assuming_token(self, key: str):
        return self.table.where(key=key).delete()

    def _current_lock(self, key: str):
        return self.table.where(key=key).get_dict(
            'lock_token',
            'locked_until',
            type=StoreRecord,
        )

    def set(self, key: str, value: Value, token: float):
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

    def ask_set(self, key: str, value: Value):
        with self.ask_token(key) as token:
            if not token:
                return False
            self.__set_assuming_token(key, value)
        return False

    def wait_del(self, key: str, request_every: float = 0.02,
                 timeout: Optional[float] = 3):
        wait = self.wait_token(
            key,
            request_every=request_every,
            timeout=timeout,
        )
        with wait:
            self.__del_assuming_token(key)

    def wait_set(
        self,
        key: str,
        value: Value,
        request_every: float = 0.02,
        timeout: Optional[float] = 3,
    ):
        wait = self.wait_token(
            key,
            request_every=request_every,
            timeout=timeout,
        )
        with wait as token:
            self.set(key, value, token)

    @contextmanager
    def ask_token(
        self,
        *keys: str,
        max_duration: float = 0.5,
    ):
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
                if not self._ask_access(
                        key,
                        token=token,
                        max_duration=max_duration,
                ):
                    raise TokenError(key, token)
            yield
        finally:
            for key in keys:
                self._unlock(key, token, max_duration)
        return

    @contextmanager
    def wait_token(
        self,
        *keys: str,
        max_duration: float = 0.5,
        request_every: float = 0.02,
        timeout: Optional[float] = 3,
    ):
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
        did = self.table.where(key=key).and_where_sql(
            """
            lock_token<0 OR
            lock_token=? OR
            locked_until<?
            """,
            token,
            now,
        ).update_or_ignore(
            lock_token=token,
            locked_until=until,
        )
        if did:  # Race winner
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
            self.table.where(key=key).update(lock_token=-1)
        return
