# app/utils/db.py
from sqlalchemy.types import TypeDecorator, JSON, Text, String
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
import json


class JSONBType(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


class TSVectorType(TypeDecorator):
    """Represents a TSVECTOR column, falls back to Text
    for non-PostgreSQL databases."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(TSVECTOR())
        else:
            return dialect.type_descriptor(Text())


class ArrayType(TypeDecorator):
    """Enables Array storage by encoding and decoding on the fly."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import ARRAY
            return dialect.type_descriptor(ARRAY(String))
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return value
        return json.loads(value)
