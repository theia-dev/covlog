import time
from datetime import datetime, date

from flask import current_app, flash
from flask import redirect, url_for, request
from flask import render_template
from flask import session

from app import db
from . import main
from .. import models


@main.context_processor
def inject_dict_for_all_templates():
    return dict(orga_name=current_app.config['ORGANIZATION_NAME'],
                version=current_app.config['VERSION'], client=get_client(),
                today=date.today().isoformat())


def get_client():
    try:
        client = models.Client.query.get(session['client'])
    except KeyError:
        client = None
    return client


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/log')
def log_event():
    client = get_client()
    if client:
        show_exit = request.args.get('show_exit', type=bool, default=False)
        location_code = request.args.get('location_code', type=str, default=None)
        log_limit = None
        if show_exit:
            event = client.events[-1]
            if event.active is True:
                log_limit = models.Location.query.get(event.location_id)
            else:
                flash('You are not registered at a location at the moment.', ' warning')
        if location_code is not None:
            log_limit = models.Location.query.filter_by(code=location_code).first()
        return render_template('log.html', log_limit=log_limit)
    else:
        return redirect(url_for('main.index'))


@main.route('/register', methods=('GET', 'POST'))
def register():
    if get_client():
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        gt = request.form['group-token'].strip()
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        group = models.Group.query.filter_by(token=gt).first()
        if group is None:
            time.sleep(2)
            flash('Group token is invalid!', 'error')
            return redirect(url_for('main.register'))
        client = models.Client()

        client.group_id = group.id
        client.name = name
        client.email = email

        db.session.add(client)
        db.session.commit()
        session['client'] = client.id
        session.permanent = True
        flash('Registered successfully.', 'succes')
        return redirect(url_for('main.client_hub'))
    return render_template('register.html', rtype='normal')


@main.route('/quick_register/<token>', methods=('GET', 'POST'))
def quick_register(token):
    if get_client():
        return redirect(url_for('main.log_event'))
    group = models.Group.verify_auth_token(token)
    if not group:
        time.sleep(2)
        flash('Group token is invalid!', 'error')
        return redirect(url_for('main.register'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        client = models.Client()

        client.group_id = group.id
        client.name = name
        client.email = email
        db.session.add(client)
        db.session.commit()
        session['client'] = client.id
        session.permanent = True
        flash('Registered successfully.', 'succes')
        return redirect(url_for('main.client_hub'))
    return render_template('register.html', rtype='quick')


@main.route('/login', methods=('GET', 'POST'))
def login():
    if get_client():
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        gt = request.form['group-token'].strip()
        ct = request.form['client_token'].strip()
        group = models.Group.query.filter_by(token=gt).first()
        if group is None:
            time.sleep(2)
            flash('Group token is invalid!', 'error')
            return redirect(url_for('main.login'))
        client = models.Client.query.filter_by(token=ct).first()
        if client is None:
            time.sleep(2)
            flash('Client token is invalid!', 'error')
            return redirect(url_for('main.login'))
        if client.group != group:
            time.sleep(2)
            flash('Group token is invalid!', 'error')
            return redirect(url_for('main.login'))
        session['client'] = client.id
        session.permanent = True
        flash('Login successful.', 'success')
        return redirect(url_for('main.log_event'))
    return render_template('login.html')


@main.route('/quick_login/<token>')
def quick_login(token):
    client = models.Client.verify_auth_token(token)
    if client:
        session['client'] = client.id
        session.permanent = True
        return redirect(url_for('main.log_event'))
    else:
        return redirect(url_for('main.index'))


@main.route('/logout')
def logout():
    del session['client']
    session.modified = True
    flash('Logged out!', 'neutral')
    return redirect(url_for('main.index'))


@main.route('/client')
def client_hub():
    if get_client():
        return render_template('client.html')
    else:
        return redirect(url_for('main.index'))


@main.route('/enter', methods=('POST', 'GET'))
def log_enter_now():
    client = get_client()
    if client is None:
        return redirect(url_for('main.index'))
    if request.method == 'GET':
        return redirect(url_for('main.log_event'))
    if request.method == 'POST':
        location_code = request.form['location_code'].strip()
        print(location_code)
        location = models.Location.query.filter_by(code=location_code).first()
        if not location:
            flash('Wrong location ID.', 'warning')
        if location not in client.group.locations:
            flash(f'{location.code} is not registered for your group.', 'warning')
        if client.is_present():
            flash('You are already at a location.', 'warning')
        if location.capacity > location.usage:
            new_event = models.Event()
            new_event.location_id = location.id
            new_event.client_id = client.id
            db.session.add(new_event)
            db.session.commit()
        else:
            flash(f'{location.code} is at capacity. Please do not enter!', 'warning')
        return redirect(url_for('main.log_event'))


@main.route('/enter/<location_code>')
def log_enter(location_code):
    client = get_client()
    if client is None:
        flash('You need to be registered!', 'warning')
        return redirect(url_for('main.index'))
    location = models.Location.query.filter_by(code=location_code).first()
    if not location:
        flash('Wrong location ID.', 'warning')
        return redirect(url_for('main.log_event'))

    if location not in client.group.locations:
        flash(f'{location.code} is not registered for your group.', 'warning')
        return redirect(url_for('main.log_event'))

    if location.capacity <= location.usage:
        flash(f'{location.code} is at capacity. Please do not enter!', 'warning')
    return redirect(url_for('main.log_event', location_code=location_code))


@main.route('/exit', methods=('GET', 'POST'))
def log_exit():
    client = get_client()
    if not client:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        if client is None:
            return redirect(url_for('main.index'))
        event = client.events[-1]
        if event.active is True:
            event.active = False
            event.date_out = datetime.now()
            db.session.commit()
        return redirect(url_for('main.log_event'))
    return redirect(url_for('main.log_event', show_exit=True))
