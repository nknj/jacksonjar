#!/usr/bin/env python3

from jacksonjar import db

db.reflect()
db.drop_all()
db.create_all()
