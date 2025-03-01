import datetime
import json
import sys
from dataclasses import dataclass as vanilla_dataclass
from decimal import Decimal
from enum import Enum
from ipaddress import IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface, IPv6Network
from pathlib import Path
from typing import List
from uuid import UUID

import pytest

from pydantic import BaseModel, create_model
from pydantic.color import Color
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.json import pydantic_encoder, timedelta_isoformat
from pydantic.types import DirectoryPath, FilePath, SecretBytes, SecretStr


class MyEnum(Enum):
    foo = 'bar'
    snap = 'crackle'


@pytest.mark.parametrize(
    'input,output',
    [
        (UUID('ebcdab58-6eb8-46fb-a190-d07a33e9eac8'), '"ebcdab58-6eb8-46fb-a190-d07a33e9eac8"'),
        (IPv4Address('192.168.0.1'), '"192.168.0.1"'),
        (Color('#000'), '"black"'),
        (Color((1, 12, 123)), '"#010c7b"'),
        (SecretStr('abcd'), '"**********"'),
        (SecretStr(''), '""'),
        (SecretBytes(b'xyz'), '"**********"'),
        (SecretBytes(b''), '""'),
        (IPv6Address('::1:0:1'), '"::1:0:1"'),
        (IPv4Interface('192.168.0.0/24'), '"192.168.0.0/24"'),
        (IPv6Interface('2001:db00::/120'), '"2001:db00::/120"'),
        (IPv4Network('192.168.0.0/24'), '"192.168.0.0/24"'),
        (IPv6Network('2001:db00::/120'), '"2001:db00::/120"'),
        (datetime.datetime(2032, 1, 1, 1, 1), '"2032-01-01T01:01:00"'),
        (datetime.datetime(2032, 1, 1, 1, 1, tzinfo=datetime.timezone.utc), '"2032-01-01T01:01:00+00:00"'),
        (datetime.datetime(2032, 1, 1), '"2032-01-01T00:00:00"'),
        (datetime.time(12, 34, 56), '"12:34:56"'),
        (datetime.timedelta(days=12, seconds=34, microseconds=56), '1036834.000056'),
        ({1, 2, 3}, '[1, 2, 3]'),
        (frozenset([1, 2, 3]), '[1, 2, 3]'),
        ((v for v in range(4)), '[0, 1, 2, 3]'),
        (b'this is bytes', '"this is bytes"'),
        (Decimal('12.34'), '12.34'),
        (create_model('BarModel', a='b', c='d')(), '{"a": "b", "c": "d"}'),
        (MyEnum.foo, '"bar"'),
    ],
)
def test_encoding(input, output):
    assert output == json.dumps(input, default=pydantic_encoder)


@pytest.mark.skipif(sys.platform.startswith('win'), reason='paths look different on windows')
def test_path_encoding(tmpdir):
    class PathModel(BaseModel):
        path: Path
        file_path: FilePath
        dir_path: DirectoryPath

    tmpdir = Path(tmpdir)
    file_path = tmpdir / 'bar'
    file_path.touch()
    dir_path = tmpdir / 'baz'
    dir_path.mkdir()
    model = PathModel(path=Path('/path/test/example/'), file_path=file_path, dir_path=dir_path)
    expected = '{{"path": "/path/test/example", "file_path": "{}", "dir_path": "{}"}}'.format(file_path, dir_path)
    assert json.dumps(model, default=pydantic_encoder) == expected


def test_model_encoding():
    class ModelA(BaseModel):
        x: int
        y: str

    class Model(BaseModel):
        a: float
        b: bytes
        c: Decimal
        d: ModelA

    m = Model(a=10.2, b='foobar', c=10.2, d={'x': 123, 'y': '123'})
    assert m.dict() == {'a': 10.2, 'b': b'foobar', 'c': Decimal('10.2'), 'd': {'x': 123, 'y': '123'}}
    assert m.json() == '{"a": 10.2, "b": "foobar", "c": 10.2, "d": {"x": 123, "y": "123"}}'
    assert m.json(exclude={'b'}) == '{"a": 10.2, "c": 10.2, "d": {"x": 123, "y": "123"}}'


def test_invalid_model():
    class Foo:
        pass

    with pytest.raises(TypeError):
        json.dumps(Foo, default=pydantic_encoder)


@pytest.mark.parametrize(
    'input,output',
    [
        (datetime.timedelta(days=12, seconds=34, microseconds=56), 'P12DT0H0M34.000056S'),
        (datetime.timedelta(days=1001, hours=1, minutes=2, seconds=3, microseconds=654_321), 'P1001DT1H2M3.654321S'),
    ],
)
def test_iso_timedelta(input, output):
    assert output == timedelta_isoformat(input)


def test_custom_encoder():
    class Model(BaseModel):
        x: datetime.timedelta
        y: Decimal
        z: datetime.date

        class Config:
            json_encoders = {datetime.timedelta: lambda v: f'{v.total_seconds():0.3f}s', Decimal: lambda v: 'a decimal'}

    assert Model(x=123, y=5, z='2032-06-01').json() == '{"x": "123.000s", "y": "a decimal", "z": "2032-06-01"}'


def test_custom_iso_timedelta():
    class Model(BaseModel):
        x: datetime.timedelta

        class Config:
            json_encoders = {datetime.timedelta: timedelta_isoformat}

    m = Model(x=123)
    assert m.json() == '{"x": "P0DT0H2M3.000000S"}'


def test_custom_encoder_arg():
    class Model(BaseModel):
        x: datetime.timedelta

    m = Model(x=123)
    assert m.json() == '{"x": 123.0}'
    assert m.json(encoder=lambda v: '__default__') == '{"x": "__default__"}'


def test_encode_dataclass():
    @vanilla_dataclass
    class Foo:
        bar: int
        spam: str

    f = Foo(bar=123, spam='apple pie')
    assert '{"bar": 123, "spam": "apple pie"}' == json.dumps(f, default=pydantic_encoder)


def test_encode_pydantic_dataclass():
    @pydantic_dataclass
    class Foo:
        bar: int
        spam: str

    f = Foo(bar=123, spam='apple pie')
    assert '{"bar": 123, "spam": "apple pie"}' == json.dumps(f, default=pydantic_encoder)


def test_encode_custom_root():
    class Model(BaseModel):
        __root__: List[str]

    assert Model(__root__=['a', 'b']).json() == '["a", "b"]'
