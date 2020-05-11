import random
from base64 import _b32alphabet
from datetime import datetime
from functools import partial

from flask_security import UserMixin, RoleMixin
from itsdangerous import (JSONWebSignatureSerializer
                          as Serializer, BadSignature, SignatureExpired)

from . import Config
from . import db

token_alphabet = _b32alphabet.decode()
token_fixes = {'1': 'I', '0': 'O', '8': 'B'}


def create_token(length=6):
    return ''.join([random.choice(token_alphabet) for _ in range(length)])


def prepare_token(token, length=6):
    if len(token) != length:
        return None
    for key, value in token_fixes.values():
        token = token.replace(key, value)
    for element in token:
        if element not in token_alphabet:
            return None
    return token


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name


# Define models
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

    def __str__(self):
        return self.email


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(6), unique=True, default=partial(create_token, length=6))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    active = db.Column(db.Boolean(), default=True)
    created = db.Column(db.TIMESTAMP, default=datetime.today())
    events = db.relationship('Event', backref='client')

    def is_present(self, get_location=False):
        if self.events:
            if get_location:
                return self.events[-1].active, self.events[-1].location
            else:
                return self.events[-1].active
        else:
            if get_location:
                return False, None
            else:
                return False

    def get_auth_token(self):
        s = Serializer(Config.SECRET_KEY_TOKEN, salt='client_token_auth')
        return s.dumps({'id': self.id})

    @classmethod
    def verify_auth_token(cls, token):
        s = Serializer(Config.SECRET_KEY_TOKEN, salt='client_token_auth')
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None  # valid token, but expired
        except BadSignature:
            return None  # invalid token
        else:
            return cls.query.get(data['id'])

    @classmethod
    def get_list(cls):
        c_list = []
        for client in cls.query.all():
            value = client.token
            if client.name:
                value += f' ({client.name})'
            c_list.append([client.id, value])
        return c_list

    @property
    def location_codes(self):
        return [loc.code for loc in self.group.locations]

    def __repr__(self):
        if self.name:
            return self.name
        else:
            return self.token


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(12), default=partial(create_token, length=12))
    name = db.Column(db.String(255))
    created = db.Column(db.TIMESTAMP, default=datetime.today())
    clients = db.relationship('Client', backref='group')
    locations = db.relationship('Location', secondary='group_location', back_populates='groups')

    @classmethod
    def get_list(cls):
        return [(entry.id, entry.name) for entry in cls.query.all()]

    def get_auth_token(self):
        s = Serializer(Config.SECRET_KEY_TOKEN, salt='group_token_auth')
        return s.dumps({'id': self.id})

    @classmethod
    def verify_auth_token(cls, token):
        s = Serializer(Config.SECRET_KEY_TOKEN, salt='group_token_auth')
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None  # valid token, but expired
        except BadSignature:
            return None  # invalid token
        else:
            return cls.query.get(data['id'])

    def __repr__(self):
        if self.name:
            return self.name
        else:
            return self.token


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(7), unique=True)
    name = db.Column(db.String(127))
    address = db.Column(db.String(255))
    email = db.Column(db.String(255))
    capacity = db.Column(db.Integer)
    responsible = db.Column(db.String(255))
    groups = db.relationship('Group', secondary='group_location', back_populates='locations')
    events = db.relationship('Event', backref='location')
    created = db.Column(db.TIMESTAMP, default=datetime.today())

    @property
    def usage(self):
        return sum([e.active for e in self.events])

    @classmethod
    def get_list(cls):
        l_list = []
        for location in cls.query.all():
            if cls.code:
                value = location.code
            elif cls.name:
                value = location.name
            else:
                value = location.token
            l_list.append([location.id, value])
        return l_list

    def __repr__(self):
        if self.code:
            return self.code
        elif self.name:
            return self.name
        else:
            return self.token


class GroupLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    date_in = db.Column(db.DateTime, default=datetime.now())
    date_out = db.Column(db.DateTime, default=None)
    active = db.Column(db.Boolean, default=True)
    expired = db.Column(db.Boolean, default=False)
