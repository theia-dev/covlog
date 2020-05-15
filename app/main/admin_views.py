import os
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta

import qrcode
from cityhash import CityHash32
from flask import current_app, send_file
from flask import redirect, url_for, flash
from flask_admin import BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_security import current_user
from flask_security.utils import hash_password
from pylatexenc.latexencode import unicode_to_latex as u2tex
from werkzeug.utils import secure_filename
from wtforms import PasswordField

from app import db
from .. import admin, models, tex_env


def get_qr_pdf(data):
    hash_base = '|'.join([str(content) for content in data.values()])
    sec_name = secure_filename(data['name'])
    build_folder = current_app.config['BUILD_FOLDER'] / f'{data["type"]}' / f'{sec_name}_{CityHash32(hash_base):x}'
    final_pdf = build_folder / f"{sec_name}.pdf"
    if final_pdf.is_file():
        return final_pdf
    build_folder.mkdir(exist_ok=True, parents=True)

    qr_raw = qrcode.QRCode()
    qr_raw.add_data(data['qr_code'])
    qr_raw.make(fit=True)
    data['qr_binary'] = ''.join([''.join([str(int(value)) for value in row]) for row in qr_raw.modules])
    data['qr_modules_count'] = qr_raw.modules_count
    data['qr_error'] = qr_raw.error_correction

    template = tex_env.get_template(f'{data["type"]}.tex')
    aux_template = tex_env.get_template('quick.aux')
    content = template.render(**data)
    aux_content = aux_template.render(**data)

    build_file = (build_folder / f"{sec_name}.tex")
    build_file.write_text(content)
    aux_file = (build_folder / f"{sec_name}.aux")
    aux_file.write_text(aux_content)
    last_wd = os.curdir
    os.chdir(build_file.parent)

    result = subprocess.call(['xelatex', '--interaction=batchmode', '--halt-on-error',
                              '--file-line-error', build_file.name], stdout=open(os.devnull, 'wb'))
    if result is not 0:
        current_app.logger.error(f'xelatex failed for {data["type"]}')
        return None

    os.chdir(last_wd)
    if final_pdf.is_file():
        for folder in build_folder.parent.glob(f'{sec_name}_*'):
            if folder.name != build_folder.name:
                shutil.rmtree(folder)
        return final_pdf
    else:
        return None


def build_trace(trace):
    if trace.client:
        client_events = models.Event.query.filter_by(client=trace.client).filter(models.Event.date_out >= trace.start).filter(models.Event.date_in <= trace.stop)
        direct_events = []
        indirect_events = []
        indirect_locations = defaultdict(lambda: dict(start=datetime.max, stop=datetime.min))
        for event in client_events:
            # started before
            direct_events += models.Event.query.filter(models.Event.date_in <= event.date_in,
                                                       models.Event.date_out >= event.date_in)
            # started during
            direct_events += models.Event.query.filter(models.Event.date_in > event.date_in,
                                                       models.Event.date_in <= event.date_out)
            indirect_locations[event.location_id]['start'] = min(event.date_in,
                                                                 indirect_locations[event.location_id]['start'])
            indirect_locations[event.location_id]['stop'] = max(event.date_out,
                                                                indirect_locations[event.location_id]['stop'])

        trace.direct_clients = list(set([de.client for de in direct_events]).difference([trace.client]))
        for location_id, value in indirect_locations.items():
            value['stop'] += timedelta(hours=trace.length)
            # started before
            indirect_events += models.Event.query.filter_by(location_id=location_id).filter(
                models.Event.date_in <= value['start'],
                models.Event.date_out >= value['start'])
            # started during
            indirect_events += models.Event.query.filter_by(location_id=location_id).filter(
                models.Event.date_in > value['start'],
                models.Event.date_in <= value['stop'])
        trace.indirect_clients = list(set([ie.client for ie in indirect_events]).difference(trace.direct_clients + [trace.client]))
    return trace


class MyModelView(ModelView):
    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False

        if current_user.has_role('superuser'):
            return True
        if current_user.has_role('user'):
            return True

        return False


class MyBaseView(BaseView):
    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False

        if current_user.has_role('superuser'):
            return True
        if current_user.has_role('user'):
            return True

        return False


class UserView(MyModelView):
    can_create = False
    can_edit = True
    can_delete = False
    form_extra_fields = {
        'password2': PasswordField('Password')
    }

    column_exclude_list = ['password', 'confirmed_at', 'role']

    form_columns = [
            'email',
            'password2',
            'first_name',
            'last_name',
            'active'
        ]

    def is_visible(self):
        if current_user.has_role('superuser'):
            return False
        else:
            return True

    def on_model_change(self, form, user, is_created):
        if not current_user.has_role('superuser'):
            if current_user.id != user.id:
                raise PermissionError('You are not allowed to alter this user!')

        if form.password2.data is not None:
            user.password = hash_password(form.password2.data)


class SuperUserView(MyModelView):
    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False

        if current_user.has_role('superuser'):
            return True

        return False
    can_create = True
    can_edit = True
    can_delete = True
    form_extra_fields = {
        'password2': PasswordField('Password')
    }

    column_exclude_list = ['password']

    form_columns = [
            'email',
            'password2',
            'first_name',
            'last_name',
            'active',
            'roles'
        ]

    def on_model_change(self, form, user, is_created):
        if not current_user.has_role('superuser'):
            if current_user.id != user.id:
                raise PermissionError('You are not allowed to alter this user!')

        if form.password2.data is not None:
            user.password = hash_password(form.password2.data)


class LimitedView(MyModelView):

    @staticmethod
    def when_superuser():
        if current_user:
            if current_user.has_role('superuser'):
                return True
        return False

    @property
    def can_create(self):
        return self.when_superuser()

    @property
    def can_edit(self):
        return self.when_superuser()

    @property
    def can_delete(self):
        return self.when_superuser()


class ToolView(MyBaseView):
    def is_visible(self):
        return False

    @expose('/')
    def index(self):
        return redirect(url_for('admin.index'))


class QRView(MyBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/qr.html',
                           l_list=models.Location.get_list(),
                           g_list=models.Group.get_list())

    @expose('group/<group_id>')
    def group(self, group_id):
        group = models.Group.query.get_or_404(group_id)
        qr_code = f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.quick_register', token=group.get_auth_token())}"
        return self.render('admin/qr_detail.html', qr_type='Group', qr_name=group.name, qr_code=qr_code,
                           pdf=url_for('qr.group_pdf', group_id=group_id))

    @expose('exit')
    def exit(self):
        qr_code = f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.log_exit')}"
        return self.render('admin/qr_detail.html', qr_type='Exit', qr_name='all', qr_code=qr_code,
                           pdf=url_for('qr.exit_pdf'))

    @expose('location/<location_id>')
    def location(self, location_id):
        location = models.Location.query.get_or_404(location_id)
        qr_code = f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.log_enter', location_code=location.code)}"
        return self.render('admin/qr_detail.html', qr_type='Location', qr_name=str(location), qr_code=qr_code,
                           pdf=url_for('qr.location_pdf', location_id=location_id))

    @expose('group/<group_id>/download')
    def group_pdf(self, group_id):
        group = models.Group.query.get_or_404(group_id)
        data = dict(
            name=u2tex(str(group)),
            type='group',
            qr_code=f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.quick_register', token=group.get_auth_token())}",
            url=f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.index')}",
        )
        pdf_file = get_qr_pdf(data)
        if pdf_file:
            return send_file(str(pdf_file.absolute()), mimetype='application/pdf',
                             attachment_filename=f'covlog_group_{pdf_file.name}', as_attachment=True)
        else:
            flash('PDF build failed!', 'error')
            return redirect(url_for('qr.group', group_id=group_id))

    @expose('location/<location_id>/download')
    def location_pdf(self, location_id):
        location = models.Location.query.get_or_404(location_id)
        data = dict(
            name=location.code,
            type='enter',
            qr_code=f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.log_enter', location_code=location.code)}",
            long_name=u2tex(location.name_or_address),
            url=f"{current_app.config['SERVER_NAME_PDF']}{url_for('main.log_enter', location_code=location.code)}",

        )
        pdf_file = get_qr_pdf(data)
        if pdf_file:
            return send_file(str(pdf_file.absolute()), mimetype='application/pdf',
                             attachment_filename=f'covlog_location_{pdf_file.name}', as_attachment=True)
        else:
            flash('PDF build failed!', 'error')
            return redirect(url_for('qr.location', loction_id=location_id))

    @expose('exit/download')
    def exit_pdf(self):
        data = dict(
            type='exit',
            name='all',
            qr_code=f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.log_exit')}",
            url=f"{current_app.config['SERVER_NAME_PDF']}{url_for('main.log_exit')}"
        )
        pdf_file = get_qr_pdf(data)
        if pdf_file:
            return send_file(str(pdf_file.absolute()), mimetype='application/pdf',
                             attachment_filename=f'covlog_exit_{pdf_file.name}', as_attachment=True)
        else:
            flash('PDF build failed!', 'error')
            return redirect(url_for('qr.exit'))


class TraceView(MyModelView):
    can_view_details = True
    column_exclude_list = ['description', 'contact_mail', 'length']

    form_columns = [
        'token',
        'client',
        'location',
        'title',
        'description',
        'contact',
        'contact_mail',
        'start',
        'stop',
        'length',
        'active',
    ]

    details_template = "admin/details_trace.html"

    @expose('report/plaintext/<token>')
    def plaintext_report(self, token):
        trace = models.Trace.query.filter_by(token=token).first()
        if not trace:
            flash("Can't create report for unknown trace!")
            return redirect(url_for('trace.index_view'))
        url = f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.trace_detail', token=trace.token)}"
        return self.render('admin/plaintext_report.html', trace=trace, url=url)

    @expose('report/pdf/<token>')
    def pdf_report(self, token):
        trace = models.Trace.query.filter_by(token=token).first()
        if trace is None:
            flash("Can't create report for unknown trace!")
            return redirect(url_for('trace.index_view'))
        data = dict(
            type='trace',
            name=trace.long_name,
            trace=trace,
            qr_code=f"https://{current_app.config['SERVER_NAME_PDF']}{url_for('main.trace_detail', token=trace.token)}",
            url=f"{current_app.config['SERVER_NAME_PDF']}{url_for('main.trace_detail', token=trace.token)}"
        )
        pdf_file = get_qr_pdf(data)
        if pdf_file:
            return send_file(str(pdf_file.absolute()), mimetype='application/pdf',
                             attachment_filename=f'covlog_report_{pdf_file.name}', as_attachment=True)
        else:
            flash(f'PDF build failed for {trace.token}!', 'error')
            return redirect(url_for('trace.details_view', id=trace.id))

    def on_model_change(self, form, trace, is_created):
        if trace.location and trace.client:
            raise AssertionError('A trace has to be based either on a client or a location!')
        if trace.start is None:
            raise AssertionError('A trace need a start time.')
        if trace.start is not None:
            if trace.start > trace.stop:
                raise AssertionError('Start time needs to be before stop time.')
        if trace.length < 0:
            raise AssertionError('Length should not be negative.')
        trace = build_trace(trace)


admin.add_view(QRView(name='QR', endpoint='qr'))
admin.add_view(ToolView(name='Tools', endpoint='tool'))

admin.add_view(TraceView(models.Trace, db.session))
admin.add_view(MyModelView(models.Group, db.session, category='CL DB'))
admin.add_view(MyModelView(models.Location, db.session, category='CL DB'))
admin.add_view(MyModelView(models.Client, db.session, category='CL DB'))
admin.add_view(LimitedView(models.Event, db.session, category='CL DB'))
admin.add_view(UserView(models.User, db.session, name='Admins'))
admin.add_view(SuperUserView(models.User, db.session, name='Admins', endpoint='superuser'))
