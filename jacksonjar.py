#!/usr/bin/env python3

import os
import sys
import stripe
import urllib
import requests
import logging
from datetime import datetime

from flask import Flask, render_template, request,\
    redirect, url_for, session, g, flash
from flask.ext.sqlalchemy import SQLAlchemy


# Config
app = Flask(__name__, static_url_path='/static')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SITE'] = 'https://connect.stripe.com'
app.config['AUTHORIZE_URI'] = '/oauth/authorize'
app.config['TOKEN_URI'] = '/oauth/token'
app.config['CLIENT_ID'] = os.environ['CLIENT_ID']
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['PUBLISHABLE_KEY'] = os.environ['PUBLISHABLE_KEY']
app.config['JACKSON_CENTS'] = 2000

# Logging
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

# SQLAlchemy Init
db = SQLAlchemy(app)


# Stripe Init
stripe.api_key = app.config['SECRET_KEY']


# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stripe_user_id = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(254))
    name = db.Column(db.String(50))
    phone = db.Column(db.String(10))

    url = db.Column(db.String(512))
    country = db.Column(db.String(2))
    currency = db.Column(db.String(3))

    stripe_publishable_key = db.Column(db.String(50))
    stripe_secret_key = db.Column(db.String(50))
    refresh_token = db.Column(db.String(100))

    donations = db.relationship('Donation', backref='user', lazy='dynamic')

    def __init__(self, stripe_user_id, stripe_publishable_key,
                 stripe_secret_key, refresh_token):
        self.stripe_user_id = stripe_user_id
        self.stripe_publishable_key = stripe_publishable_key
        self.stripe_secret_key = stripe_secret_key
        self.refresh_token = refresh_token

    def count_verbose(self):
        if self.donations.count() == 1:
            return '1 Jackson'
        else:
            return self.donations.count() + ' Jacksons'

    def __repr__(self):
        return '<User %r>' % self.stripe_user_id


class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stripe_charge_id = db.Column(db.String(50), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    donator_email = db.Column(db.String(254))
    amount = db.Column(db.Integer)
    time = db.Column(db.DateTime)

    def __init__(self, stripe_charge_id, user_id, donator_email,
                 time=None, amount=None):
        self.stripe_charge_id = stripe_charge_id
        self.user_id = user_id
        self.donator_email = donator_email
        self.time = time or datetime.utcnow()
        self.amount = amount or app.config['JACKSON_CENTS']

    def __repr__(self):
        return '<Donation %r>' % self.stripe_charge_id


# Middlwear
@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])


# Routes

# Basic
@app.route('/')
def index():
    if g.user:
        return redirect(url_for('home'))
    else:
        total_jackson_count = Donation.query.count()
        # TODO: change to Donation groupby on userid
        total_user_count = User.query.count()
        return render_template(
            'index.html',
            total_jackson_count=total_jackson_count,
            total_user_count=total_user_count
        )


@app.route('/home')
def home():
    if g.user:
        return render_template(
            'home.html',
            user=g.user,
            key=app.config['PUBLISHABLE_KEY']
        )
    else:
        return redirect(url_for('index'))


@app.route('/jar/<int:user_id>')
def jar(user_id):
    # Get user for donation
    # TODO: handle error if user not found
    user = User.query.get(user_id)

    return render_template(
        'jar.html',
        user=user,
        key=app.config['PUBLISHABLE_KEY']
    )


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logout Successful - See you soon!', 'info')
    return redirect(url_for('index'))


# Charge Card
@app.route('/charge/<int:user_id>', methods=['POST'])
def charge(user_id):
    # Get user for donation
    # TODO: handle error if user not found
    user = User.query.get(user_id)

    token = request.form['stripeToken']
    donator_email = request.form['stripeEmail']

    # Charge the card and save the donation
    # TODO: handle case when charge fails
    charge = stripe.Charge.create(
        source=token,
        amount=app.config['JACKSON_CENTS'],
        currency='usd',
        description='Jackson for ' + user.stripe_user_id +
                    ' by ' + donator_email,
        destination=user.stripe_user_id,
        application_fee=100
    )
    donation = Donation(
        stripe_charge_id=charge.id,
        user_id=user.id,
        donator_email=donator_email
    )
    db.session.add(donation)
    db.session.commit()

    return redirect(url_for('thanks', user_id=user.id))


@app.route('/thanks/<int:user_id>')
def thanks(user_id):
    # Get user for donation
    # TODO: handle error if user not found
    user = User.query.get(user_id)

    return render_template(
        'thanks.html',
        user=user
    )


# oAuth
@app.route('/authorize')
def authorize():
    site = app.config['SITE'] + app.config['AUTHORIZE_URI']
    params = {
        'response_type': 'code',
        'scope': 'read_write',
        'client_id': app.config['CLIENT_ID']
    }

    # Redirect to Stripe /oauth/authorize endpoint
    url = site + '?' + urllib.parse.urlencode(params)
    return redirect(url)


@app.route('/oauth/callback')
def callback():
    code = request.args.get('code')
    data = {
        'grant_type': 'authorization_code',
        'client_id': app.config['CLIENT_ID'],
        'client_secret': app.config['SECRET_KEY'],
        'code': code
     }

    # Make /oauth/token endpoint POST request
    url = app.config['SITE'] + app.config['TOKEN_URI']
    resp = requests.post(url, params=data)

    # Save successful response as user
    # TODO: handle unsuccessful response
    user = User.query.filter_by(
        stripe_user_id=resp.json().get('stripe_user_id')).first()
    if not user:
        user = User(
            stripe_user_id=resp.json().get('stripe_user_id'),
            stripe_publishable_key=resp.json().get('stripe_publishable_key'),
            stripe_secret_key=resp.json().get('access_token'),
            refresh_token=resp.json().get('refresh_token')
        )

    # Add/update additional data on user
    account = stripe.Account.retrieve(id=resp.json().get('stripe_user_id'))
    user.email = account.email
    user.name = account.display_name
    user.phone = account.support_phone
    user.url = account.business_url
    user.country = account.country
    user.currency = account.default_currency

    db.session.add(user)
    db.session.commit()

    # Log user in
    session['user_id'] = user.id

    # TODO: handle request and DB exceptions & show errors
    return redirect(url_for('home'))

# Run
if __name__ == '__main__':
    app.run(debug=True)
