#!/usr/bin/env python3

import os
import sys
import urllib
import logging
from datetime import datetime

import stripe
import requests

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
        total_user_count = Donation.query.distinct(Donation.user_id).count()
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


@app.route('/details')
def details():
    if g.user:
        return render_template(
            'details.html',
            user=g.user
        )
    else:
        return redirect(url_for('index'))


@app.route('/jar/<int:user_id>')
def jar(user_id):
    user = User.query.get(user_id)
    if user:
        return render_template(
            'jar.html',
            user=user,
            key=app.config['PUBLISHABLE_KEY']
        )
    else:
        return render_template(
            '404.html',
            error='This Jar doesn\'t exist!'
        ), 404


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logout Successful - See you soon!', 'info')
    return redirect(url_for('index'))


# Charge Card
@app.route('/charge/<int:user_id>', methods=['POST'])
def charge(user_id):
    user = User.query.get(user_id)
    if user:
        token = request.form['stripeToken']
        donator_email = request.form['stripeEmail']

        # Charge the card and save the donation
        try:
            charge = stripe.Charge.create(
                source=token,
                amount=app.config['JACKSON_CENTS'],
                currency='usd',
                description='Jackson for ' + user.stripe_user_id +
                            ' by ' + donator_email,
                destination=user.stripe_user_id,
                application_fee=100
            )
        except stripe.error.CardError as e:
            flash('Your card was declined.', 'error')
            return redirect(url_for('jar', user_id=user.id))

        donation = Donation(
            stripe_charge_id=charge.id,
            user_id=user.id,
            donator_email=donator_email
        )

        db.session.add(donation)
        db.session.commit()

        return redirect(url_for('thanks', user_id=user.id))
    else:
        return render_template(
            '404.html',
            error='Charge unsuccessful - jar doesn\'t exist!'
        ), 404


@app.route('/thanks/<int:user_id>')
def thanks(user_id):
    user = User.query.get(user_id)

    # User is optional in template
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
    data = resp.json()

    # Save successful response as user
    if not data.get('error'):
        user = User.query.filter_by(
            stripe_user_id=data.get('stripe_user_id')).first()
        if not user:
            user = User(
                stripe_user_id=data.get('stripe_user_id'),
                stripe_publishable_key=data.get('stripe_publishable_key'),
                stripe_secret_key=data.get('access_token'),
                refresh_token=data.get('refresh_token')
            )

        # Add/update additional data on user
        account = stripe.Account.retrieve(id=data.get('stripe_user_id'))
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
    else:
        flash('Stripe connection failed - please try again [' +
              data.get('error') + ']', 'warning')

    return redirect(url_for('home'))


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.data and request.data.type == 'account.updated':
        account = request.data.data.object
        user = User.query.filter_by(stripe_user_id=account.id).first()
        if user:
            user.email = account.email
            user.name = account.display_name
            user.phone = account.support_phone
            user.url = account.business_url
            user.country = account.country
            user.currency = account.default_currency

            db.session.add(user)
            db.session.commit()

    return ''


# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# Util
def prettydate(d):
    diff = datetime.utcnow() - d
    s = diff.seconds
    if diff.days > 7 or diff.days < 0:
        return d.strftime('%d %b %y')
    elif diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '{} days ago'.format(diff.days)
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{} seconds ago'.format(s)
    elif s < 120:
        return '1 minute ago'
    elif s < 3600:
        return '{} minutes ago'.format(round(s/60))
    elif s < 7200:
        return '1 hour ago'
    else:
        return '{} hours ago'.format(round(s/3600))
app.jinja_env.globals.update(prettydate=prettydate)

# Run
if __name__ == '__main__':
    app.run(debug=True)
