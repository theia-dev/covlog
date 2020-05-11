import os
import subprocess

from flask import redirect, url_for, flash
from flask import current_app, send_file
from flask_admin import BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_security import current_user
from flask_security.utils import hash_password
from werkzeug.utils import secure_filename
from wtforms import PasswordField

from app import db
from .. import admin, models, tex_env


def get_qr_pdf(data):

    sec_name = secure_filename(data['name'])
    build_folder = current_app.config['BUILD_FOLDER'] / f'{data["type"]}_{sec_name}'
    final_pdf = build_folder / f"{sec_name}.pdf"
    if final_pdf.is_file():
        return final_pdf
    build_folder.mkdir(exist_ok=True, parents=True)

    template = tex_env.get_template(f'{data["type"]}.tex')

    content = template.render(**data)

    build_file = (build_folder / f"{sec_name}.tex")
    build_file.write_text(content)
    last_wd = os.curdir
    os.chdir(build_file.parent)

    for _ in range(2):
        result = subprocess.call(['xelatex', '--interaction=batchmode', '--halt-on-error',
                                  '--file-line-error', build_file.name], stdout=open(os.devnull, 'wb'))
        if result is not 0:
            current_app.logger.error(f'xelatex failed for {data["type"]}')
            return None

    os.chdir(last_wd)
    if final_pdf.is_file():
        return final_pdf
    else:
        return None


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

    def on_model_change(self, form, user, is_created):
        if not current_user.has_role('superuser'):
            if current_user.id != user.id:
                raise PermissionError('You are not allowed to alter this user!')

        if form.password2.data is not None:
            print(form.password2.data)
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
            print(form.password2.data)
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

    @expose('add_admin')
    def add_admin(self):
        return self.render('admin/add_admin.html')


class ReportView(MyBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/report.html',
                           c_list=models.Client.get_list(),
                           l_list=models.Location.get_list(),
                           g_list=models.Group.get_list())


class QRView(MyBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/qr.html',
                           l_list=models.Location.get_list(),
                           g_list=models.Group.get_list())

    @expose('group/<group_id>')
    def group(self, group_id):
        group = models.Group.query.get_or_404(group_id)
        qr_code = url_for('main.quick_register', token=group.get_auth_token(), _external=True)
        return self.render('admin/qr_detail.html', qr_type='Group', qr_name=group.name, qr_code=qr_code,
                           pdf=url_for('qr.group_pdf', group_id=group_id))

    @expose('exit')
    def exit(self):
        qr_code = url_for('main.log_exit', _external=True)
        return self.render('admin/qr_detail.html', qr_type='Exit', qr_name='all', qr_code=qr_code,
                           pdf=url_for('qr.exit_pdf'))

    @expose('location/<location_id>')
    def location(self, location_id):
        location = models.Location.query.get_or_404(location_id)
        qr_code = url_for('main.log_enter', location_code=location.code, _external=True)
        return self.render('admin/qr_detail.html', qr_type='Location', qr_name=str(location), qr_code=qr_code,
                           pdf=url_for('qr.location_pdf', location_id=location_id))

    @expose('group/<group_id>/download')
    def group_pdf(self, group_id):
        group = models.Group.query.get_or_404(group_id)
        data = dict(
            name=str(group),
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
            long_name=location.name_or_address,
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


admin.add_view(ReportView(name='Reports', endpoint='report'))
admin.add_view(QRView(name='QR', endpoint='qr'))
admin.add_view(ToolView(name='Tools', endpoint='tool'))

admin.add_view(MyModelView(models.Group, db.session))
admin.add_view(MyModelView(models.Location, db.session))
admin.add_view(MyModelView(models.Client, db.session))
admin.add_view(LimitedView(models.Event, db.session))
admin.add_view(UserView(models.User, db.session))
admin.add_view(SuperUserView(models.User, db.session, name='SuperUser', endpoint='superuser'))
