#!/usr/bin/python3.5
# -*- coding: utf-8 -*-

from flask import Flask
from dotenv import load_dotenv
import os

from flask import Flask, redirect, render_template, request, url_for,  \
        session, send_from_directory, render_template_string, Response
from time import sleep
from flask import jsonify, g
import requests
from functools import wraps
from peewee import *
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict, dict_to_model

from datetime import datetime as dt
from datetime import timedelta as tdelta

import jinja_try_catch ## echodata 4.0
import babel.dates
from dateutil.relativedelta import relativedelta

from random import choice as randomchoice

import sqlite3 as sqlite

import json

from werkzeug.utils import secure_filename
import bleach
import csv
import re
import html2text, markdown
from html import escape as html_escape

from uuid import uuid4
from hashlib import sha256

from flask_sslify import SSLify

from flask_mail import Mail, Message

# Connects echoview with echodata
from echoconnections import *
# Translation of echo terms to Russian module
from translate import *
# DICOM SR report extraction module
from dicomecho import *

# Template form 4.0 creation module
from form_from_xlsx import form_from_xlsx
import io # for search and csv output




app = Flask(__name__) #, static_folder='static', static_url_path='')
load_dotenv()

from openai import OpenAI
client = OpenAI()


app.config["DEBUG"] = os.getenv("DEBUG", 'True').lower() == 'true'


ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'doc', 'docx', 'zip', 'png', 'jpg', 'jpeg', 'gif', 'odt', 'xlsx'])

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = int(os.getenv('SEND_FILE_MAX_AGE_DEFAULT', 0))
app.config['TEMPLATES_AUTO_RELOAD'] = os.getenv('TEMPLATES_AUTO_RELOAD', 'True').lower() == 'true'

mail=Mail(app)

db_url = os.getenv("DATABASE_URL", 'mysql://okhotin:okhotin@localhost/okhotin')
db=connect(db_url)

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", '/Users/okhotin/Dropbox/echoview/working copy/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.jinja_env.globals['hasattr'] = hasattr

app.config["dicom_server"] = os.getenv("DICOM_SERVER",'192.168.31.100')
app.config["dicom_aet"] = os.getenv("DICOM_AET", 'VALSALVA')
app.config["dicom_client"] = os.getenv("DICOM_CLIENT", 'Artemijs-MacBook')
app.config["dicom_port"] = int(os.getenv("DICOM_PORT", "4242"))


app.config.update(
	MAIL_SERVER=os.getenv("MAIL_SERVER", 'smtp.gmail.com'),
	MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
	MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "True").lower()=="true",
	MAIL_USE_SSL=os.getenv("MAIL_USE_SSL", "False").lower()=="true",
	MAIL_USERNAME = os.getenv("MAIL_USER_NAME", 'dr.okhotin@gmail.com'),
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", 'dr.okhotin@gmail.com'),
	MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

	)
app.config["admins"] = os.getenv("ADMINS").split(',')
app.config["code_word"] = os.getenv("CODE_WORD")


    
mail=Mail(app)



@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = 60*60 # datetime.timedelta(minutes=20)
    session.modified = True
    #flask.g.user = flask_login.current_user
    try:
        db.connect()
    except:
        db.close()
        db.connect()
    try:
        currentsession = Session.get(id=session['stored'])
        if currentsession.status:
            currentsession.end = dt.now()+tdelta(hours=1)
            currentsession.save()
    except:
        pass

@app.after_request
def after_request(response):
    db.close()
    return response

#sslify = SSLify(app)

class MediumTextField(TextField):
    field_type = 'MEDIUMTEXT'

class Doctor(Model):
    name = CharField()
    surname = CharField()
    profession = CharField() # врач, медсестра, технический работник
    specialty = CharField()  #
    signature = TextField()
    ward = CharField()
    email = CharField()
    phone = CharField()
    passwordhash = CharField()
    privileges = CharField()  # admin, physician, nurse
    active = IntegerField(default=1)
# status   (admin, registered, payed)
    class Meta:
        database = db

class Session(Model):
    whose = ForeignKeyField(Doctor, related_name='sessions')
    session_id = CharField(default=1)
    beginning = DateTimeField()
    end = DateTimeField()
    ip = CharField()
    status = BooleanField(default=True)
    class Meta:
        database = db


class Patient(Model):
    name = CharField()         # имя
    surname = CharField()      # фамилия
    fathername = CharField()   # отчество
    dob = DateTimeField()      # дата рождения
    sex = CharField()          # пол
    address = CharField()      # адрес
    phone = CharField()        # телефон
    email = CharField()        # электронный адрес
    comments = TextField(default='')     # комментарии
    uniqueid = CharField(default='')     # уникальный идентификатор
    status = IntegerField(default=1) # статус (?)
    class Meta:
        database = db

class CurrentStatus(Model):
    patient = ForeignKeyField(Patient, related_name='currentstatus')  # к какому пациенту относится
    inpatient = IntegerField(default=0) # в стационаре ли
    ward = CharField()                 # отделение
    alive =  IntegerField(default=1)   # жив ли
    medications = CharField()       # текущие назначения (медикаменты и пр.)
    diagnosis = TextField()         # диагноз
    problemlist = TextField()       # проблемный лист
    doctor = CharField()            # основной врач
    data = TextField()              # поле дополнительных данных (json)
    lastvisit = DateTimeField()     # последний визит
    plannedvisit = DateTimeField()  # время планируемого визита
    comments =  CharField()         # комментарии
    tags =  CharField()         # тэги (AVR, MVR, CABG  и пр.)
    class Meta:
        database = db

class Record(Model):
    patient = ForeignKeyField(Patient, related_name='records')  # пациент к которому относится запись
    title = CharField()     # название
    sort = CharField()      # сорт записи (консультация, выписка, дневник, анализ, исследование, документ)
    contents = MediumTextField()  # основное содержание
    data = TextField()      # данные
    html = TextField()      # html-формат записи
    recorddate = DateTimeField()   # дата к которой относится запись
    created = DateTimeField()   # дата создания в базе
    modified = DateTimeField()  # дата последней версии в базе
    author = ForeignKeyField(Doctor, related_name='records')  # создатель записи
    active = BooleanField(default=True)   # активна ли запись (удалена?)
    version = IntegerField(default=1)     # версия (номер)
    class Meta:
        database = db

class Record_old(Model):   # для хранения старых версий записей
    current = ForeignKeyField(Record, related_name='versions')
    title = CharField()     # название
    sort = CharField()      # сорт записи (консультация, выписка, дневник, анализ, исследование, документ)
    contents = MediumTextField()  # основное содержание
    html = TextField()      # html-формат записи
    data = TextField()      # данные
    recorddate = DateTimeField()   # дата к которой относится запись
    created = DateTimeField()   # дата создания в базе
    modified = DateTimeField()  # дата последней версии в базе
    active = BooleanField(default=True)   # активна ли запись (удалена?)
    version = IntegerField(default=1)     # версия (номер)
    class Meta:
        database = db

class Datarecord(Model):
    patient = ForeignKeyField(Patient, related_name='datarecords')  # пациент к которому относится запись
    record = ForeignKeyField(Record, related_name='datarecords')  # запись, к которой относятся данные
    name = CharField()     # название
    value = FloatField()
    text = TextField()
    low = FloatField()
    high = FloatField()
    units = CharField()
    sample = CharField()
    test = CharField()
    date = DateTimeField()   # дата к которой относится запись
    created = DateTimeField()   # дата создания в базе
    modified = DateTimeField()  # дата последней версии в базе
    author = ForeignKeyField(Doctor, related_name='datarecords')  # создатель записи
    active = BooleanField(default=True)   # активна ли запись (удалена?)
    class Meta:
        database = db

class Attachment(Model):     # файлы-приложения (без версий)
    active = BooleanField(default=True)
    extension = CharField() # расширение (pdf, avi  и пр.)
    filename = CharField()
    record = ForeignKeyField(Record, related_name='attachments')
    class Meta:
        database = db


class Template(Model):             # шаблоны записей
    active = BooleanField(default=True)
    title = CharField()
    sort = CharField()
    contents = MediumTextField()
    comments = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    author = ForeignKeyField(Doctor, related_name='templates')
    class Meta:
        database = db

class Template_old(Model):       # шаблоны записей (старые версии)
    active = BooleanField(default=True)
    title = CharField()
    sort = CharField()
    contents = MediumTextField()
    comments = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    author = ForeignKeyField(Doctor, related_name='templates_old')
    current = ForeignKeyField(Template, related_name='versions')
    class Meta:
        database = db

class TemplateForm(Model):       # шаблоны форм (4.0)
    active = BooleanField(default=True)
    title = CharField()
    description = CharField()
    sort = CharField()
    xlsx_file = CharField()
    template_html = MediumTextField()
    template_print = MediumTextField()
    comments = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    author = ForeignKeyField(Doctor, related_name='templates_form')
    class Meta:
        database = db


class Data(Model):              # единицы хранения данных в записях (data), формат пока не разработан
    abbreviation = CharField()
    json = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    author = ForeignKeyField(Doctor, related_name='data')
    class Meta:
        database = db

class Data_old(Model):        # единицы хранения данных в записях (data), формат пока не разработан (старые версии)
    abbreviation = CharField()
    json = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    current = ForeignKeyField(Data, related_name='versions')
    class Meta:
        database = db


class Query(Model):             # запросы для быстрого вставления в текст (формат пока не разработан)
    abbreviation = CharField()
    query = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    author = ForeignKeyField(Doctor, related_name='queries')
    class Meta:
        database = db

class Query_old(Model):            # запросы (старые версии) для быстрого вставления в текст
    abbreviation = CharField()
    query = TextField()
    created = DateTimeField()
    modified = DateTimeField()
    version = IntegerField(default=1)
    current = ForeignKeyField(Query, related_name='versions')
    class Meta:
        database = db

class Ward(Model):
    title = CharField()
    description = TextField()
    template = ForeignKeyField(Template, related_name='wards')
    locations = TextField() #  room1 bed1 bed2 bed3) / room2 bed1 bed2 bed3
    active = BooleanField(default=True)
    class Meta:
        database = db

class Wardprivilege(Model):
    ward = ForeignKeyField(Ward, related_name='doctors')
    doctor = ForeignKeyField(Doctor, related_name='wards')
    status = CharField(default='doctor')  # doctor, chief, noaccess
    class Meta:
        database = db


class Status(Model):
    ward = ForeignKeyField(Ward, related_name='patients')
    patient = ForeignKeyField(Patient, related_name='wards')
    admission = DateTimeField()
    discharge = DateTimeField()
    followup = DateTimeField()
    status = CharField() # admitted/discharged/discarded
    data = TextField() # json, status data based on template
    template = TextField()
    datemodified = DateTimeField()
    whomodified = ForeignKeyField(Doctor)
    whoincharge = ForeignKeyField(Doctor, related_name='inchargefor')
    location = CharField()
    class Meta:
        database = db

class Config(Model):
    author = ForeignKeyField(Doctor, related_name='config')
    head = TextField(default='')
    footer = TextField(default='')
    hospital = CharField(default='')
    ward = CharField(default='')
    templates = TextField(default='')
    default = BooleanField(default=False)
    class Meta:
        database = db

class Configs(Model):
    author = ForeignKeyField(Doctor, related_name='configs')
    label = TextField(default='')
    data = TextField(default='')
    version = IntegerField(default=1)
    date = DateTimeField()
    class Meta:
        database = db



def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', nexturl=request.url, error='Для доступа нужно войти в систему.'))
        if session['username'].lower() not in app.config["admins"]:
            return redirect(url_for('login', nexturl=request.url, error='Недостаточно привилегий.'))
        try:
            g.doctor = Doctor.get(Doctor.email==session['username'])
        except:
            return redirect(url_for('logout'))            
        return f(*args, **kwargs)
    return decorated_function



@app.route('/dicom')
def dicom():
    studies = get_studies(app.config['dicom_server'],
                          app.config['dicom_aet'],
                          app.config['dicom_client'],
                          port=app.config['dicom_port'])
    return render_template('dicom_studies.html', studies=studies)

@app.route('/dicomall')
def dicomall():
    total_obs=[]
    studies = get_studies(app.config['dicom_server'],
                          app.config['dicom_aet'],
                          app.config['dicom_client'],
                          port=app.config['dicom_port'])
    for study in studies:
        srs = retrieve_comprehensive_srs(
            server_ip=app.config['dicom_server'],
            server_aet=app.config['dicom_aet'],
            study_instance_uid=study.StudyInstanceUID,
            client_aet=app.config['dicom_client'],
            port=app.config['dicom_port'])
        try:
            observations = unique_decode(srs[0]['content']['observations'])
            metadata = srs[0].copy()
            metadata.pop('content')
            total_obs.append(observations)
        except:
            observations = [{'Finding Site': 'No SR report'}]
            metadata = {}
    return Response(str(total_obs), mimetype='text/csv',
               headers={"Content-Disposition":"attachment;filename=output.csv"})


@app.route('/dicom_sr_report/<uuid>')
def dicom_sr_report(uuid):

    srs = retrieve_comprehensive_srs(
        server_ip=app.config['dicom_server'],
        server_aet=app.config['dicom_aet'],
        study_instance_uid=uuid,
        client_aet=app.config['dicom_client'],
        port=app.config['dicom_port'])
        
    try:
        observations = unique_decode(srs[0]['content']['observations'])
        metadata = srs[0].copy()
        metadata.pop('content')
    except:
        observations = [{'Finding Site': 'No SR report'}]
        metadata = {}


    try:
        conf = Configs.get(Configs.label == 'dicom_conversion_table')
        data = json.loads(conf.data)
        filename = data.get('filename')
        file_path= os.path.join(app.config['UPLOAD_FOLDER'], filename)
    except:
        return('No DICOM translation table!')


    
    echo, values = dicom_to_echo(observations = observations,
                                 metadata = metadata,
                                 file_path=file_path)
#    return str(echo)
#    return f"{str(metadata)} <p><p> {str(observations)}"
    return render_template('dicom_sr_report.html', observations=observations, metadata=metadata)


@app.route('/dicom_sr_report_raw/<uuid>')
def dicom_sr_report_raw(uuid):

    srs = retrieve_comprehensive_srs(
        server_ip=app.config['dicom_server'],
        server_aet=app.config['dicom_aet'],
        study_instance_uid=uuid,
        client_aet=app.config['dicom_client'],
        port=app.config['dicom_port'])
        
    try:
        observations = unique_decode(srs[0]['content']['observations'])
        metadata = srs[0].copy()
        metadata.pop('content')
    except:
        observations = [{'Finding Site': 'No SR report'}]
        metadata = {}


    try:
        conf = Configs.get(Configs.label == 'dicom_conversion_table')
        data = json.loads(conf.data)
        filename = data.get('filename')
        file_path= os.path.join(app.config['UPLOAD_FOLDER'], filename)
    except:
        return('No DICOM translation table!')

    
    
    echo, values = dicom_to_echo(observations = observations,
                                 metadata = metadata,
                                 file_path=file_path)
    html_echo = [f'<tr><td>{k}</td><td>{v}</td></tr>' for k,v in echo.items()]
    html_echo = '<table>'+'\n'.join(html_echo)+'</table>'

    html_values = [f'<tr><td>{k}</td><td>{str(v)}</td></tr>' for k,v in values.items()]
    html_values = '<table>'+'\n'.join(html_values)+'</table>'

    return html_echo + html_values
#    return f"{str(metadata)} <p><p> {str(observations)}"
    return render_template('dicom_sr_report.html', observations=observations, metadata=metadata)


## dicomconversion table upload
@app.route('/dicomconversion', methods=['GET', 'POST'])
@admin_required
def dicomconversion():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename != '' and file and allowed_file(file.filename):
            filename = unique_secure_filename(file.filename, 0)
            file_path= os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            try:
                conf = Configs.get(Configs.label == 'dicom_conversion_table')
            except:
                conf = Configs.create(author = g.doctor, label = 'dicom_conversion_table', data ="{}", date = dt.now(), version = 1)
            if conf.data != "{}":
                # remove previous uploaded xlsx if present
                data = json.loads(conf.data)
                old_filename = data.get('filename', '')
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_filename)
                try:
                    os.remove(old_path)
                except OSError:
                    app.logger.exception("Failed to remove old dicom conversion table: %s", old_path)
            
            conf.data = json.dumps({"filename": filename})
            conf.date = dt.now()
            conf.version = conf.version+1
            conf.save()
    else:
        try:
            conf = Configs.get(Configs.label == 'dicom_conversion_table')
        except:
            conf = Configs.create(author = g.doctor, version = 0, label = 'dicom_conversion_table', data = "{}", date = dt.now())
        
    data = json.loads(conf.data)
    filename = data.get('filename', '')
    return render_template('dicomconversion.html', filename = filename)


@app.route('/viewimages')
def viewimages():
    return render_template('viewimages.html')


@app.route('/getoldtb')
@admin_required
def getolddb():
    echodata = Doctor.get(email='echodata@echodata.ru')
    connection = sqlite.connect('patients.db')
    cursor = connection.cursor()
    query = "SELECT id FROM patients WHERE deleted=0"
    query_patient = "SELECT * FROM patients WHERE (id={}) AND (deleted=0)"
    query_exams = "SELECT * FROM examinations WHERE (patient_id={}) and (deleted=0)"
    cursor.execute(query)
    patients = cursor.fetchall()
    a=[]
    for p_id in patients:
        cursor.execute(query_patient.format(p_id[0]))
        p = cursor.fetchone()
        try:
            sex = ('м' if (p[4]=='м' or p[3]=='' or p[3][-1]!='а') else 'ж')
        except:
            sex = 'м'
        try:
            dob = dt(year=int(p[5][0:4]), month = int(p[5][4:6]), day = int(p[5][6:8]))
        except:
            dob = dt(year=1901, month=1, day=1)


        pc, new = Patient.get_or_create(
            name = '{}'.format(p[2].strip()),
            surname = '{}'.format(p[1].strip()),
            fathername = '{}'.format(p[3].strip()),
            dob = dob, defaults = {
            'sex':sex,
            'address': '{}'.format(p[6]), 'phone': '{}'.format(p[7]), 'email':'',
            'comments': '{}\n{}'.format(p[10], p[9]),
            'uniqueid': 'old{}'.format(p[0])})
        print(pc.uniqueid, pc.surname, new)
        cursor.execute(query_exams.format(p_id[0]))
        exams = cursor.fetchall()
        for exam in exams:
            if exam[3]=='консультация': sort='консультация'
            elif exam[3]=='выписка': sort='выписка'
            elif exam[3]=='госпитализация': sort='статус'
            elif exam[3]=='эхокардиография': sort='исследование'
            elif exam[3] in ['стресс-эхокардиография', 'нормальная стресс-эхо', 'чреспищеводная эхокардиография']: sort='исследование'
            elif exam[3] in ['катетеризация центральной вены', 'плевральная пункция', 'электрическая кардиоверсия']: sort='процедура'
            else: sort='другое'
            try:
                examdate = dt(year=int(exam[2][0:4]), month = int(exam[2][4:6]), day = int(exam[2][6:8]))
            except:
                examdate = dt(year=1901, month=1, day=1)
            contents = exam[4].replace('\r', '').replace('\n', '  \n')
            Record.create(
                patient = pc, title = exam[3], sort = sort,
                contents = contents, html = markdn(contents),
                data='', recorddate=examdate, created = examdate, modified = examdate,
                author = echodata)
    connection.close()
    return render_template("plainprint.html", message='Done', messages='')







@app.route('/init')
#@admin_required
def init():
    # Create the tables.
    #db.drop_tables([Doctor, Patient, Session, CurrentStatus, Record, Record_old, Attachment, Template, Template_old, Query, Query_old, Data, Data_old])
    # db.drop_tables([CurrentStatus, Datarecord])
    # db.drop_tables([Attachment, Record_old, Status])
    # db.drop_tables([Record])
    # db.drop_tables([Patient])
    # db.create_tables([Datarecord, Doctor, Patient, Session, CurrentStatus, Record, Record_old, Attachment,
    #                  Template, Template_old, Query, Query_old, Data, Data_old], safe=True)
    #db.create_tables([Ward, Config, Status, Wardprivilege], safe=True)
    #db.drop_tables([TemplateForm], safe=True)
    #db.create_tables([TemplateForm], safe=True)
    #db.drop_tables([Configs])
    #db.create_tables([Configs], safe=True)

    return 'Tables created'



def hash_password(password):
    # uuid is used to generate a random number
    salt = uuid4().hex
    return sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == sha256(salt.encode() + user_password.encode()).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', nexturl=request.url, error='Для доступа нужно войти в систему.'))
        #if sessi
        g.ip=request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        try:
            g.doctor = Doctor.get(Doctor.email==session['username'])
        except:
            return redirect(url_for('logout'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def indexx():
    return redirect(url_for('index'))

@app.route('/index')
@login_required
def index():
    if 'username' in session:
        return render_template('index.html', admin=(session['username'] in app.config["admins"]))
    else:
        return redirect(url_for('login', nexturl=request.url, error='Для доступа нужно войти в систему.'))



@app.route('/openai/<id>', methods=['GET', 'POST'])
@login_required
def openai(id):
    if request.method == 'POST':
        prompt = request.form['prompt']
        date_after = request.form.get('date_after', (dt.now()-tdelta(days=30)).strftime('%Y-%m-%d'))
        date_before = request.form.get('date_before', (dt.now()-tdelta(days=30)).strftime('%Y-%m-%d'))
        records = Record.select().where((Record.patient==id) & (Record.recorddate >= date_after) & (Record.recorddate <= date_before)).order_by(Record.recorddate.desc())
        patient = Patient.get(Patient.id==id)
        all_records = "\nСледующая запись\n".join([f"Дата {rec.recorddate}, {html2text.html2text(rec.html)}" for rec in records])
        all_records = all_records.replace(patient.name, "ИМЯ_ПАЦИЕНТА").replace(patient.surname, "ФАМИЛИЯ_ПАЦИЕНТА")
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты помощник врача. "
                    "Анализируй историю болезни пациента и давай осторожные, "
                    "осмотрительные рекомендации. Никогда не ставь окончательный диагноз "
                    "и не отменяй назначения врача."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"История болезни пациента:\n\n{all_records}\n\n"
                    f"Вопрос врача:\n{prompt}"
                ),
            },
        ]

        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",  # or another current model
                messages=messages
            )
            answer = response.choices[0].message.content
        except Exception as e:
            CHAD_API_KEY = os.getenv("CHAD_API_KEY", '')
            request_json = {
                "message": prompt,
                "api_key": CHAD_API_KEY,
                "history": messages
            }
            response = requests.post(url='https://ask.chadgpt.ru/api/public/gpt-5-mini',
                         json=request_json)
            
            if response.status_code != 200:
                return(f'Ошибка! Код http-ответа: {response.status_code}')
            else:
                resp_json = response.json()
            if resp_json['is_success']:
                answer = f"{resp_json['response']}\nИспользовано слов:{resp_json['used_words_count']}"
            else:
                answer = f"Ошибка: {resp_json['error_message']}"

        return render_template('openai.html', id=id, prompt=prompt, answer=answer, patient=patient, date_after=date_after, date_before=date_before)
    patient = Patient.get(Patient.id==id)
    return render_template('openai.html', id=id, patient=patient, 
                           date_after = (dt.now()-tdelta(days=30)).strftime('%Y-%m-%d'),
                           date_before = (dt.now()).strftime('%Y-%m-%d'))



@app.route('/wards', methods=['GET', 'POST'])   # основная страница отделений (на входе отделение и пациент, не обязательно)
@login_required
def wards():
    pid = request.args.get('patient', '')
    wid = request.args.get('ward', '')
    wards=Ward.select().where(Ward.active).order_by(Ward.title)
    try:
        w=Ward.get((Ward.id==wid) & (Ward.active))
    except:
        wid=''
        w=None
        if len(wards)!=0:
            w = wards[0]
            wid=w.id

    try:
        status=(Status.select()
                      .where((Status.patient==pid) & (Status.ward==wid) & (Status.status=='admitted'))
                      .order_by(Status.location).get())
    except:
        status=None
        if w!=None:
            if len(w.patients)!=0:
                try:
                    status = (Status.select()
                                    .where((Status.ward==w) & (Status.status=='admitted'))
                                    .order_by(Status.location).get())
                except:
                    pass
    return render_template('wards-main.html', wards=wards, ward=w, status=status)


@app.route('/config')   # настройки
@login_required
def config():
    return render_template('config-bi.html', wards=wards)


@app.route('/wardsconfig')   # список клиник
@login_required
def wardsconfig():
    wards=Ward.select().where(Ward.active).order_by(Ward.title)
    return render_template('wards-config.html', wards=wards)

@app.route('/wardpatients/<wid>')   # список клиник
@login_required
def wardpatients(wid):
    wrd=Ward.get((Ward.id==wid) & (Ward.active))
    patients=Status.select().where((Status.ward==wrd) & (Status.status=='admitted'))
    return render_template('ward-patients.html', patients=patients, wid=wid)


@app.route('/wardslist')   # список клиник
@login_required
def wardslist():
#    wards=Ward.select().where(Ward.active)
    wards=Wardprivilege.select().where((Wardprivilege.status=='chief'))
    return render_template('wards.html', wards=wards)



@app.route('/ward/<wid>', methods=['GET', 'POST'])   # настройки клиники
@login_required
def ward(wid):
    kill=request.args.get('kill', 0)
    if kill=='1' and wid!=0:
        ward=Ward.get((Ward.id==wid))
        ward.active=False
        ward.save()
        ww=Ward.select().where(Ward.active)
        if (len(ww)>0): wid=ww[0].id
        else: wid=0
    if request.method=='POST':
        w={}
        w['title']=request.form['title']
        w['description'] = request.form['description']
        template_id = request.form['template']
        w['template'] = Template.get(Template.id==template_id)
        chief_id = request.form['chief']
#        w['chief'] = Doctor.get(Doctor.id==chief_id)
        w['locations'] = request.form['locations']
        if int(wid)==0:
            newward=Ward.create(**w)
            wp=Wardprivilege.create(ward = newward, doctor = Doctor.get(id=chief_id))
            wp.status='chief'
            wp.save()
        else:
            query=Ward.update(**w).where(Ward.id==wid)
            query.execute()
            newward=Ward.get((Ward.id==wid))
            Wardprivilege.get_or_create(ward = newward, doctor = Doctor.get(id=chief_id), defaults={'status':'chief'})
        return redirect(url_for('ward', wid=newward.id))
    templates=Template.select().where(Template.sort=='клиника')
    doctors = Doctor.select()
    if int(wid)!=0:
        ward=Ward.get((Ward.id==wid))
        chief = Wardprivilege.get((Wardprivilege.ward==ward) & (Wardprivilege.status=='chief'))
        return render_template("wardconfig.html", templates=templates, doctors=doctors, mode=init, ward=ward, chief=chief.doctor.id)
    return render_template("wardconfig.html", templates=templates, doctors=doctors, mode=init)


@app.route('/admit/<pid>', methods=['GET', 'POST'])   # госпитализировать пациента
@login_required
def admit(pid):
    if request.method=='POST':
        st={}
        wid=request.form['ward']
        st['ward']=wid

#            patient.dob = dt.strptime('{:02d}-{:02d}-{:04d}'.format(int(request.form['month']), int(request.form['day']), int(request.form['year'])), '%m-%d-%Y')
        admission_date = dt.strptime(request.form['record_date'], '%Y-%m-%d')
#                    dt.strptime(date_str, "%Y-%m-%d %H:%M")

 #       year = int(request.form['year'])
 #       month = int(request.form['month'])
 #       day = int(request.form['day'])
 #       hour = int(request.form['hour'])
 #       minute = int(request.form['minute'])
        st['admission'] = admission_date
        st['patient']=pid
        st['discharge']=st['admission']
        st['followup']=st['admission']
        st['status']='admitted'
        st['data']=''
        wrd = Ward.get((Ward.id==st['ward']) & (Ward.active))
        templ = wrd.template
        st['template']=templ.contents
        st['datemodified']=st['admission']
        st['whomodified']=g.doctor.id
        st['whoincharge']=g.doctor.id
        st['location']=''
        newst, created = Status.get_or_create(patient=pid, status='admitted', ward=wid, defaults=st)
        return redirect(url_for('status', sid=newst.id))
    patient=Patient.get(Patient.id==pid)
    wards=Ward.select().where(Ward.active)
    return render_template('admit.html', patient=patient, wards=wards,
        dateform = date_form(dt.now(), 1,1),
        timeform = time_form(dt.now()))

@app.route('/discharge/<sid>', methods=['GET', 'POST'])   # госпитализировать пациента
@login_required
def discharge(sid):
    status=Status.get(Status.id==sid)
    status.status='discharged'
    status.discharge=dt.now()
    status.save()
    return 'discharged'


@app.route('/status/<sid>', methods=['GET', 'POST'])   # статус пациента в клинике
@login_required
def status(sid):
    status = Status.get(Status.id==sid)
    if request.method=='POST':
        status.data=json.dumps(request.form)
        room = request.form.get('room')
        bed = request.form.get(room+'bed')
        status.location=room+'-'+('' if bed==None else bed)
        status.datemodified = dt.now()
        status.whomodified = g.doctor
        status.save()
        record = templatedata_to_record(status.data)
        rec = Record.create(patient=status.patient, title='Статус ({})'.format(status.ward.title),
                            sort='статус', **record, created=dt.now(), modified=dt.now(), author=g.doctor)
        for datarec in record['datarecords']:
            Datarecord.create(author=g.doctor, patient=status.patient, record=rec,
                              **datarec, created=dt.now(), modified=dt.now())

    form=template_to_form(status.template, status.patient, status.data)

    locations = status.ward.locations
    rooms = [{'room':room.split(' ')[0], 'beds':room.split(' ')[1:]} for room in locations.split('\n')]
    if '-' in status.location:
        location = {'room': status.location.split('-')[0], 'bed':status.location.split('-')[1]}
    else:
        location = {'room': status.location.split('-')[0], 'bed':''}
    return render_template("status.html", status=status, form=form, rooms=rooms, location=location)

@app.route('/printstatus/<sid>', methods=['GET', 'POST'])   # последняя запись в статусе
@login_required
def printstatus(sid):
    status = Status.get(Status.id==sid)
    try:
        record = templatedata_to_record(status.data)
        return render_template('status-print.html', record=record, status=status)
    except:
        return '''<html><body onload="if (alert('Пустой статус') || true) {window.close();}"> Статус не заполнен </body></html>'''

@app.route('/wardprintrx/<wid>',  methods=['GET', 'POST'])
@login_required
def wardprintrx(wid):
    ward = Ward.get(Ward.id==wid)
    location=request.args.get('location', '')+'%'
    status = Status.select().where((Status.ward==ward) & (Status.status=='admitted') & (Status.location ** location))
    rxs = []
    for st in status:
        rx={}
        rx['name'] = st.patient.surname + ' ' + st.patient.name + ' ' + st.patient.fathername
        rx['age'] = st.patient.dob
        rx['days'] = relativedelta(dt.now(), st.admission).days
        rx['location'] = st.location
        rx['doctor'] = st.whomodified.surname + ' ' + st.whomodified.name
        rx['date'] = st.datemodified
        r, f = data_from_status(st.id, '!назначения')
        rx['rx']=markdn(r.replace('\r', '').replace('\n', '  \n'))
        rxs.append(rx)
    return render_template('wardprintrx.html', rxs=rxs)


@app.route('/editbeforeprint',  methods=['GET', 'POST'])
def editbeforeprint():
    if request.method=='POST':
        mode = yn(request.form, 'mode')
        html = yn(request.form, 'html')
        header = yn(request.form, 'footer')
        footer = yn(request.form, 'header')
        if yn(request.form, 'format') !='html':
            html = markdn(html)
            header = markdn(header)
            footer = markdn(footer)
    else:
        html=header=footer=mode=''
    return render_template('editbeforeprint.html', header=header, html=html, footer=footer, mode=mode)


@app.route('/data_from_status/<sid>/<s>')
@login_required
def data_from_status(sid, s):
    status = Status.get(Status.id==sid)
    try:
        record = templatedata_to_record(status.data)
        data = [(d['text'], d['value']) for d in record['datarecords'] if d['name']==s]
        if len(data)>0:
            return data[0] #, data['value']
        else:
            return '', 0
    except:
        return '', 0


def filled_form_to_print(template, data, patient):
    return 1


@app.route('/search_by_age', methods=['GET', 'POST'])                           # расширенный поиск больных
@login_required
def search_by_age():
    data = {}
    words = request.args.get('words', '')
    logic = request.args.get('logic', 'and')
    for target_age in range(100):
        word_list = words.split('_')
        word_conditions = (Record.contents.contains(word)
            for word in word_list)

        word_query = None
        for cond in word_conditions:
            word_query = cond if word_query is None else word_query | cond

        age_at_record = fn.TIMESTAMPDIFF(SQL('YEAR'), Patient.dob, Record.recorddate)

#        age_at_record = fn.FLOOR(
 #           (fn.JULIANDAY(Record.recorddate) - fn.JULIANDAY(Patient.dob)) / 365.25
  #      )
        
        query = Record.select().join(Patient).where(
            (age_at_record == target_age) & word_query
        )
        

        count = Record.select().join(Patient).where(
            (age_at_record == target_age) & word_query
        ).count()
        data[target_age] = count

    rows=[['age', 'count', 'words', 'logic']]

    for age in data.keys():
        rows.append([age, data[age], words, logic])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)

    return Response(output.getvalue(), mimetype='text/csv; charset=utf-8',
                headers={"Content-Disposition": "attachment; filename=record_count.csv"})

    

    

@app.route('/search', methods=['GET', 'POST'])                           # расширенный поиск больных
@login_required
def search():
    try:
        doctor_id = Doctor.get(email=session['username'])
    except:
        return redirect(url_for('logout'))
    records=[]
    patients=[]
    csvs=recs=nowords=surname=words=after=before=sort=''
    if request.method=='POST':
        recs = yn(request.form, 'recs')
        csvs = yn(request.form, 'csvs')
        surname = yn(request.form, 'surname')
        words = yn(request.form, 'words')
        nowords = yn(request.form, 'nowords')
        sort = yn(request.form, 'sort')
        after = yn(request.form, 'after', default='1900-01-01')
        before = yn(request.form, 'before', default='2100-01-01')
        patients = Patient.select().where(Patient.surname ** (surname+'%'))
        dtn = lambda s: dt(*[int(i) for i in s.split('-')])
        records = (Record.select()
                    .where((Record.sort ** ('%' + sort + '%')) & (Record.recorddate < dtn(before)) & (Record.recorddate > dtn(after)) &
                           (Record.patient << patients))
                            )
        for word in words.split('&'):
            if word!='':
                records = Record.select().where((Record.id << records) &
                                             (Record.contents **('%'+word+'%')))

        for noword in nowords.split('&'):
            if noword!='':
                records = Record.select().where((Record.id << records) &
                                             ~(Record.contents **('%'+noword+'%')))


        patients = (Patient.select().join(Record).where(Record.id<<records).distinct()
                          .order_by(Patient.surname, Patient.name, Patient.fathername))


        #patients = set([r.patient for r in records])

    if csvs=='on':
        csv_cont=render_template('search.html', records=records, surname=surname,
                           words=words, after=after, before=before,
                           patients=patients, nowords=nowords, recs=recs, csvs=csvs)
        return Response(csv_cont, mimetype='text/csv', 
               headers={"Content-Disposition":"attachment;filename=output.csv"})

    return render_template('search.html', records=records, surname=surname,
                           words=words, after=after, before=before, sort=sort,
                           patients=patients, nowords=nowords, recs=recs, csvs=csvs)




@app.route('/search_2', methods=['GET', 'POST'])                           # расширенный поиск больных
@login_required
def search_2():
    try:
        doctor_id = Doctor.get(email=session['username'])
    except:
        return redirect(url_for('logout'))
    records=[]
    patients=[]
    csvs=recs=nowords=surname=words=after=before=sort=''
    if request.method=='POST':
        recs = yn(request.form, 'recs')
        csvs = yn(request.form, 'csvs')
        surname = yn(request.form, 'surname')
        words = yn(request.form, 'words')
        nowords = yn(request.form, 'nowords')
        title = yn(request.form, 'title')
        sort = yn(request.form, 'sort')
        after = yn(request.form, 'after', default='1900-01-01')
        before = yn(request.form, 'before', default='2100-01-01')
        patients = Patient.select().where(Patient.surname ** (surname+'%'))
        dtn = lambda s: dt(*[int(i) for i in s.split('-')])
        records = (Record.select()
                    .where((Record.sort ** ('%'+sort+'%')) & (Record.title ** ('%'+title+'%')) &
                           (Record.recorddate < dtn(before)) & (Record.recorddate > dtn(after)) &
                           (Record.patient << patients))
                            )
        for word in words.split('&'):
            if word!='':
                records = Record.select().where((Record.id << records) &
                                             (Record.contents **('%'+word+'%')))

        for noword in nowords.split('&'):
            if noword!='':
                records = Record.select().where((Record.id << records) &
                                             ~(Record.contents **('%'+noword+'%')))


        patients = (Patient.select().join(Record).where(Record.id<<records).distinct()
                          .order_by(Patient.surname, Patient.name, Patient.fathername))


        #patients = set([r.patient for r in records])

    if csvs=='on':
        csv_cont=render_template('search_2.html', records=records, surname=surname,
                           words=words, after=after, before=before,
                           patients=patients, nowords=nowords, recs=recs, csvs=csvs)
        csv_cont='['+ ',\n'.join(['{{"rec_id":"{}", "pat_id":"{}",'.format(rec.id, rec.patient) + rec.data.replace('\n', ' ')[1:] for rec in records])+']'
#        csv_cont='['+',\n'.join([rec.data.replace('\n', ' ') for rec in records])+']'
        return Response(csv_cont, mimetype='text/csv',
               headers={"Content-Disposition":"attachment;filename=output.csv"})

    return render_template('search_2.html', records=records, surname=surname,
                           words=words, after=after, before=before, sort=sort,
                           patients=patients, nowords=nowords, recs=recs, csvs=csvs)





@app.route('/research_schema', methods=['GET', 'POST']) # схема исследовательской карточки
@login_required
def research_template():
    try:
        doctor_id = Doctor.get(email=session['username'])
    except:
        return redirect(url_for('logout'))
    jsonschema = request.form.get('jsonschema', '')
    jsontext = json.dumps(request.form)
    jsontext_f = json.loads(jsontext)
    jsontext_f['jsonschema']=jsonschema
#    if jsonschema=='':
#        jsontext = json.dumps(request.form + )
    return render_template('research_schema.html', jsonschema=jsonschema, jsontext = jsontext_f, requesttext=jsontext)



@app.route('/patients', methods=['GET', 'POST'])                            # список больных
@login_required
def patients():
    try:
        doctor_id = Doctor.get(email=session['username'])
    except:
        return redirect(url_for('logout'))
    name=request.args.get('name', '')
    surname=request.args.get('surname', '')
    fathername=request.args.get('fathername', '')

    if (name+surname+fathername!=''):
        patients = (Patient
                    .select()
                    .where((Patient.name ** (name + '%')) & (Patient.fathername ** (fathername + '%')) & (Patient.surname ** (surname + '%')))
                    .order_by(Patient.surname, Patient.name, Patient.fathername))
    else:
        patients = Patient.select().order_by(Patient.surname, Patient.name, Patient.fathername)

    return render_template('patients.html', patients=patients, name=name, surname=surname, fathername=fathername)


@app.route('/records/<id>')                                                     # список исследований
@login_required
def patient(id):
    try:
        patient = Patient.get(id=id)
    except:
        return 'No such patient.'
    target=request.args.get('target', '')
    sortsin=request.args.get('sortsin', '').split('|')
    sortsout=request.args.get('sortsout', '').split('|')
    if sortsin!=['']:
        records = (Record.select().where((Record.patient==id) &
                   (Record.sort << sortsin) & ~(Record.sort << sortsout))
                   .order_by(Record.recorddate.desc()))
    else:
        records = (Record.select().where((Record.patient==id) &
                   ~(Record.sort << sortsout))
                   .order_by(Record.recorddate.desc()))



    sorts = Record.select(Record.sort).where(Record.patient==id).order_by(Record.sort.desc()).distinct()
    return render_template('records.html', records=records, patient=patient,
           today=dt.now(), target=target, sorts=sorts, sortsin=sortsin, sortsout=sortsout)

@app.route('/patient/<id>')                                                     # список исследований
@login_required
def records(id):
    patient = Patient.get(id=id)
    wards = Status.select().where((Status.patient==id) & (Status.status=='admitted'))
    if len(patient.records)>0:
        rid=patient.records.order_by(Record.recorddate)[-1].id
    else:
        rid=0
    return render_template('records-bi.html', patient=patient, wards=wards, rid=rid)


@app.route('/recordprint/<rid>', methods=['GET', 'POST'])                                                     # распечатать исследование
@login_required
def recordprint(rid):
    try:
        record = Record.get(id=rid)
        patient = record.patient
    except:
        return 'No such record.'

    try:
        config = Config.get(default=1)
    except:
        config = Config.get(author=g.doctor)

    return render_template('record-print.html', record=record, config=config)

@app.route('/recordduplicate/<rid>') # сделать дубль исследования и открыть его в режиме редактирования
@login_required
def record_duplicate(rid):
    try:
        record = Record.get(id=rid)
        patient = record.patient
    except:
        return 'Записей нет.'
    new = model_to_dict(record)
    new.pop("id")
    new['author']=g.doctor
    newrecord=dict_to_model(Record, new)
    newrecord.version=1
    newrecord.recorddate=dt.now()
    newrecord.created=dt.now()
    newrecord.modified=dt.now()
    newrecord.save()
    return redirect(url_for('record', rid=newrecord.id, m='html', n='new'))

        


@app.route('/record/<rid>', methods=['GET', 'POST'])                                                     # исследование
@login_required
def record(rid):
    try:
        record = Record.get(id=rid)
        patient = record.patient
    except:
        return 'Записей нет.'
    mode=request.args.get('m', 'view')
    isnew=request.args.get('n', 'old')

# Echodata 4.0
    
    try:
        echo = json.loads(record.data)
        templateform_id = echo.get('_templateform_id', 'None') # check if it is templateform with id or old record
    except:
        templateform_id = "None"
        

    if templateform_id != 'None':             
        return redirect(url_for("filltemplateform", rid=rid, tid=templateform_id, pid=record.patient.id, n=isnew))

# ^^^ echodata 4.0
               
    if request.method == 'POST' and record.sort == 'JSON':    # модификация исследования JSON JSON
        old = model_to_dict(record)
        old.pop("patient")
        old.pop("author")
        old.pop("id")
        old['current']=record
        Record_old.create(**old)
        record.data = json.dumps(request.form, indent = 4, ensure_ascii=False)
        record.contents = json.dumps({"schema":((json.loads(record.contents))["schema"]),
                                     "value":request.form,
                                     "default": (json.loads(record.contents))["default"]},
                                     ensure_ascii=False)

        record.modified=dt.now()
        record.version += 1
        record.save()
        mode = 'view'
        isnew = 'saved'
    elif request.method == 'POST' and record.sort != 'JSON':                              # модификация исследования
        contents = request.form['contents']
        title = request.form['title']
        sort = request.form['sort']

        date_str = ' '.join([request.form.get('record_date', "1955-05-05"),              # echodata 4.0
                               request.form.get('record_time', "22:22")])
        recorddate = dt.strptime(date_str, "%Y-%m-%d %H:%M")                             # echodata 4.0

        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '' and file and allowed_file(file.filename):
                filename = unique_secure_filename(file.filename, rid)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                Attachment.create(extension=filename.split('.')[-1], filename=filename, record=record)

        if mode=='markup':
            html = markdn(contents)
            plain = contents
        elif mode=='html':
            html = contents
            plain = html2text.html2text(html)



        old = model_to_dict(record)
        old.pop("patient")
        old.pop("author")
        old.pop("id")
        old['current']=record
        if record.author==g.doctor:  # prohibits to change other's records
            Record_old.create(**old)

            record.html = html
            record.contents = plain
            record.modified=dt.now()
            record.title=title
            record.sort=sort
            record.recorddate=recorddate
            record.version += 1
            record.save()
        mode = 'view'
        isnew = 'saved'

    if record.sort == 'JSON':
        jscont = json.loads(record.contents)
        return render_template('record_json.html', record=record, patient=patient, isnew=isnew, \
            mode=mode, date_form=date_form(record.recorddate,1,1), time_form=time_form(record.recorddate),
            view=(jscont['default'] if 'default' in jscont else 'json'),
            html=render_template_string(record.html, report=jscont['value'])
            )

    return render_template('record.html', record=record, patient=patient, isnew=isnew, \
        mode=mode, date_form=date_form(record.recorddate,1,1), time_form=time_form(record.recorddate))    # модификация/просмотр исследования занесены в темплейт (в зависимости от атрибута ?edit )

@app.route('/version/<rid>', methods=['GET', 'POST'])                                                     # исследование
@login_required
def version(rid):
    try:
        record = Record.get(id=rid)
        patient = record.patient
    except:
        return 'No such record.'
    versions = record.versions

    act = request.args.get('a', '')
    ver = request.args.get('v', 0)
    if (act=='update' and ver!=0):
        if (g.doctor==record.author):
            old = model_to_dict(record)
            old.pop("patient")
            old.pop("author")
            old.pop("id")
            old['current']=record
            Record_old.create(**old)
            version = Record_old.get(id=ver)
            record.html = version.html
            record.contents = version.contents
            record.modified=dt.now()
            record.title=version.title
            record.sort=version.sort
            record.recorddate=version.recorddate
            record.version += 1
            record.save()
            return redirect(url_for('record', rid=rid))

    return render_template('versions.html', record=record, patient=patient, \
        versions=versions)             # просмотра версий



@app.route('/newpatient', methods=['GET', 'POST'])            # завести нового больного
@login_required
def newpatient():
    if request.method == 'POST':
        pat={}
        pat['name'] = request.form['name']
        pat['surname'] = request.form['surname']
        pat['fathername'] = request.form['fathername']
        try:
            pat['dob'] = dt.strptime(request.form['record_date'], '%Y-%m-%d')
        except:
            pat['dob'] = dt.strptime('01-01-1900', '%m-%d-%Y')
        try:
            pat['sex'] = request.form['sex']
        except:
            pat['sex'] = '*'
        pat['address'] = request.form['address']
        pat['phone'] = request.form['phone']
        pat['email'] = request.form['email']
        pat['comments'] = request.form['comments']
        pat['uniqueid'] = request.form['uniqueid']

        old = Patient.select().where(
            (Patient.name==pat['name']) &
            (Patient.surname==pat['surname']) &
            (Patient.fathername==pat['fathername']) &
            (Patient.dob==pat['dob']))
        if len(old)==0:
            patient=Patient.create(**pat)
            return redirect(url_for('records', id=patient.id))
        else:
            return 'Такой больной уже есть! %d' % len(old)
    return render_template("newpatient.html", date_form=date_form(dt(year=1900, day=1, month=1), 0, dt.now().year-1900))

@app.route('/editpatient/<pid>', methods=['GET', 'POST'])            # поменять данные больного
@login_required
def edit_patient(pid):
    try:
        patient=Patient.get(id=pid)
    except:
        return('Нет такого пациента.')
    if request.method == 'POST':
        patient.name = request.form['name']
        patient.surname = request.form['surname']
        patient.fathername = request.form['fathername']
        try:
            patient.dob = dt.strptime(request.form['record_date'], '%Y-%m-%d')
            
        except:
            patient.dob = dt.strptime('01-01-1900', '%m-%d-%Y')
        try:
            patient.sex = request.form['sex']
        except:
            patient.sex = '*'
        patient.address = request.form['address']
        patient.phone = request.form['phone']
        patient.email = request.form['email']
        patient.comments = request.form['comments']

        patient.save()

#        return redirect(url_for('records', id=patient.id))

    return render_template("editpatient.html", patient=patient, date_form=date_form(patient.dob, patient.dob.year-1900, dt.now().year-patient.dob.year))




@app.route('/newrecord/<id>', methods=['GET', 'POST'])            # выбор нового исследования
@login_required
def newrecord(id):
    templates = Template.select().where(~(Template.sort ** '%бланк%'))
    try:
        patient = Patient.get(id=id)
    except:
        return 'No such patient.'

    return render_template("choosetemplate.html", id=id, templates=templates, patient=patient)

@app.route('/newform/<id>', methods=['GET', 'POST'])            # выбор нового исследования/формы (4.0)
@login_required
def newform(id):
    templates = TemplateForm.select()
    try:
        patient = Patient.get(id=id)
    except:
        return 'No such patient.'

    return render_template("choosetemplateform.html", id=id, templates=templates, patient=patient)


@app.route('/chooseform/<id>', methods=['GET', 'POST'])            # завести нового больного
@login_required
def chooseform(id):
    templates = Template.select().where(Template.sort ** '%бланк%')
    try:
        patient = Patient.get(id=id)
    except:
        return 'No such patient.'

    return render_template("chooseform.html", id=id, templates=templates, patient=patient)



@app.route('/templateforms', methods=['GET', 'POST'])            # шаблоны
@login_required
def templateforms():
    templateforms = TemplateForm.select()
    return render_template("templateforms.html", templateforms=templateforms)


@app.route('/opentemplateform/<id>', methods=['GET', 'POST'])            # шаблоны
@login_required
def opentemplateform(id):
    try:
        templateform = TemplateForm.get(id=id)
    except:
        return(f'No form {id}')
    echo = {}
    is_print = request.args.get("print") == "yes"
    if request.method=='POST':
        echo = request.form.to_dict()
    if is_print:
  #      return templateform.template_print
        return render_template_string(templateform.template_print, echo=echo)

    return render_template_string(templateform.template_html, echo=echo)





@app.route('/templates', methods=['GET', 'POST'])            # шаблоны
@login_required
def templates():
    templates = Template.select()
    return render_template("templates.html", templates=templates)


# 29-10-2025 4.0. new and edit templateform
@app.route('/newtemplateform/<id>', methods=['GET', 'POST'])
@login_required
def newtemplateform(id=0):
    if request.method == 'POST':
        try:
            template = TemplateForm.get(id=id)
            modification=True                
        except:
            template = TemaplateForm.create(
                {
                    'title': '',
                    'sort': '',
                    'description': '',
                    'comments': '',
                    'created': dt.now(),
                    'author': g.doctor,
                    'modified': dt.now(),
                    'xlsx_file': '',
                    'template_html': '',
                    'template_print': ''
                }
            )
            modification=False
            
        template.title = request.form['title']
        template.sort = request.form['sort']
        template.description = request.form['description']
        template.comments = request.form['comments']
        template.modified = dt.now()
        
        file = request.files['file']
        if template.title =='': template.title=file.filename
        if template.sort=='': template.sort="исследование"
        if file.filename != '' and file and allowed_file(file.filename):
            filename = unique_secure_filename(file.filename, 0)
            file_path= os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            if (modification):
                # remove previous uploaded xlsx if present
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], template.xlsx_file)
                try:
                    os.remove(old_path)
                except OSError:
                    app.logger.exception("Failed to remove old xlsx file: %s", old_path)
            template.xlsx_file = filename
            template_form = form_from_xlsx(title='', header=template.title, 
                                               description=template.description, file_path=file_path)
            if template_form['check']!='ok': return(template_form['check'])
            template.template_html = template_form['html']
            template.template_print = template_form['printable']
        template.save()
        return redirect(url_for('templateforms'))

    try: 
        templateform = TemplateForm.get(id=id)                
    except:
        templateform = {
            'title': '', 'sort': '', 'description': '', 'comments': '', 'id': ''
        }
    return render_template("newtemplateform.html", templateform=templateform)


@app.route('/newtemplate', methods=['GET', 'POST'])            # новый шаблон
@login_required
def newtemplate():
    if request.method == 'POST':
        title = request.form['title']
        sort = request.form['sort']
        comments = request.form['comments']
        contents = request.form['contents']
        created = dt.now()
        modified = dt.now()
        author = g.doctor
        try:
            Template.get(title=title)
            return 'Такой шаблон уже есть!'                   
        except:
            pass
              # вставить проверку шаблона на синтаксическую правильность

        template = Template.create(title=title, sort=sort, comments=comments, contents=contents,\
            created=created, modified=modified, author=author)
        return redirect(url_for('templates'))

    return render_template("newtemplate.html")


@app.route('/templatesconfig')
@login_required
def templatesconfig():
    return render_template('templates-bi.html')



@app.route('/edittemplate/<id>', methods=['GET', 'POST'])            # редактировать старый шаблон
@login_required
def edittemplate(id=0):
    if request.method == 'POST':
        title = request.form['title']
        sort = request.form['sort']
        comments = request.form['comments']
        contents = request.form['contents']
        modified = dt.now()
        author = g.doctor
        template_id = request.form['id']

        cur_temp = Template.get(id=template_id)

        Template_old.create(title = cur_temp.title, sort = cur_temp.sort, \
            comments=cur_temp.comments, contents=cur_temp.contents, \
            modified=cur_temp.modified, created = cur_temp.created,\
            author=cur_temp.author, current=cur_temp)

        cur_temp.title = title
        cur_temp.sort = sort
        cur_temp.comments = comments
        cur_temp.contents = contents
        cur_temp.modified = modified
        cur_temp.author = author
        cur_temp.version = cur_temp.version+1
        cur_temp.save()

        return redirect(url_for('edittemplate', id=id))

    return render_template("edittemplate.html", template = Template.get(id=id))


@app.route('/prefilltemplateform/<tid>/<pid>/<rid>', methods=['GET', 'POST'])
@login_required
def prefilltemplateform(tid='0', pid='0', rid='0'):
    UUID = request.args.get("UUID", "")
    if UUID!='':
        srs = retrieve_comprehensive_srs(
            server_ip=app.config['dicom_server'],
            server_aet=app.config['dicom_aet'],
            study_instance_uid=UUID,
            client_aet=app.config['dicom_client'],
            port=app.config['dicom_port'])
        try:
            observations = unique_decode(srs[0]['content']['observations'])
            metadata = srs[0].copy()
            metadata.pop('content')
        except:
            observations = [{'Finding Site': 'No SR report'}]
            metadata = {}

        try:
            conf = Configs.get(Configs.label == 'dicom_conversion_table')
            data = json.loads(conf.data)
            filename = data.get('filename')
            file_path= os.path.join(app.config['UPLOAD_FOLDER'], filename)            
        except:
            return('No DICOM translation table!')
    
        echo, values = dicom_to_echo(observations = observations,
                                     metadata = metadata,
                                     file_path = file_path) 
        session['echo_data'] = echo
        return redirect(url_for('filltemplateform', tid=tid, pid=pid, rid=rid))

    studies = get_studies(app.config['dicom_server'],
                          app.config['dicom_aet'],
                          app.config['dicom_client'],
                          port=app.config['dicom_port'])
    return render_template('dicom_studies_select.html', studies=studies)


@app.route('/templateform_raw/<tid>', methods=['GET', 'POST'])
def templateform_raw(tid='0'):
    try:
        templateform = TemplateForm.get(id=tid)
    except:
        return(f'No form {tid}')
    return(html_escape(templateform.template_html))
#$#$#$#$#$


@app.route('/filltemplateform/<tid>/<pid>/<rid>', methods=['GET', 'POST'])            # заполнить шаблон на исследование (tid -- номер шаблона, pid -- номер пациента)
@login_required
def filltemplateform(tid='0', pid='0', rid='0'):
    try:
        templateform = TemplateForm.get(id=tid)
    except:
        return(f'No form {tid}')
    try:
        patient = Patient.get(id=pid)
    except:
        return(f'No patient {pid}')

    echo = session.pop('echo_data', {})

    n = request.args.get("n", "new")
    is_old = n == "old"

    rec = None
    if request.method=='POST':
        echo = request.form.to_dict()
        echo['_templateform_id']=tid
        if rid=='0':
            
            rec = Record.create(patient=patient, 
                                title=echo.get('_title', templateform.title), 
                                sort=echo.get('_sort', templateform.sort),
                                html = "",
                                data = json.dumps(echo),
                                recorddate = dt.strptime(f"{echo['_date']} {echo['_time']}", "%Y-%m-%d %H:%M"),                      
                                contents = "",
                                created=dt.now(), modified=dt.now(), author=g.doctor)
            rec.html = render_template_string(templateform.template_print, echo=echo,
                                          patient=patient, 
                                          record=rec
                                         )
            rec.contents= html2text.html2text(rec.html)
            rec.save()
        if rid!='0':
            rec = Record.get(id=rid)

            old = model_to_dict(rec)
            old.pop("patient")
            old.pop("author")
            old.pop("id")
            old['current']=rec
            if rec.author==g.doctor:  # prohibits to change other's records
                Record_old.create(**old)
                html = render_template_string(templateform.template_print, echo=echo, patient=patient,
                                              record=rec)

                rec.html=html
                rec.data = json.dumps(echo)
                rec.contents = html2text.html2text(html)
                rec.title = echo['_title']
                rec.sort = echo['_sort']
                rec.recorddate = dt.strptime(f"{echo['_date']} {echo['_time']}", "%Y-%m-%d %H:%M")
                rec.modified = dt.now()
                rec.version+=1
                rec.save()
        return redirect(url_for("filltemplateform", rid=rec.id, pid=pid, tid=tid, n= n))
    else: # request not post
        try:
            rec = Record.get(id=rid)
            echo = json.loads(rec.data)
        except:
            rec={'recorddate': dt.now(),
                 'title': templateform.title, 
                 'sort': templateform.sort,
                 'id': 0}
    if is_old:
        try:
            config = Config.get(author=g.doctor)
        except:
            config = Config.get(default=1)
        return render_template("record_form_print.html", record=rec, config=config)

#    return html_escape(templateform.template_html)
    return render_template_string(templateform.template_html, echo=echo, patient=patient,
                                 record=rec)
    

@app.route('/filltemplate/<tid>/<pid>', methods=['GET', 'POST'])            # заполнить шаблон на исследование (tid -- номер шаблона, pid -- номер пациента)
@login_required
def filltemplate(tid=0, pid=0):
    template = Template.get(id=tid)
    patient = Patient.get(id=pid)
    if request.method == 'POST' and template.sort=='JSON':       # новая запись JSON JSON (POST)
        record={}

        record['data'] = json.dumps(request.form, indent = 4, ensure_ascii=False)
        record['contents'] = json.dumps({"schema":((json.loads(template.contents))["schema"]),
                                     "value":request.form,
                                     "default": (json.loads(template.contents))["default"]}, ensure_ascii=False)
        record['html'] = (json.loads(template.contents))["html"]
        rec = Record.create(patient=patient, title=template.title,  sort=template.sort,\
            **record, recorddate=dt.now(), created=dt.now(), modified=dt.now(), author=g.doctor)
        return redirect(url_for('record', rid=rec.id, m='view', n='new'))
    elif request.method == 'POST'  and template.sort!='JSON':
        data = json.dumps(request.form)
        record = templatedata_to_record(data)
        rec = Record.create(patient=patient, title=template.title,  sort=template.sort,\
            **record, created=dt.now(), modified=dt.now(), author=g.doctor)
        for datarec in record['datarecords']:
            Datarecord.create(author=g.doctor, patient=patient, record=rec,
                              **datarec, created=dt.now(), modified=dt.now())
        return redirect(url_for('record', rid=rec.id, m='view', n='new'))
    if template.sort=='JSON':                                 ## новая запись JSON JSON
        return render_template("filltemplate_json.html",
            patient=patient, template=template, date_form=date_form(dt.now(),1,1),
            time_form=time_form(dt.now()))
    else:
        return render_template("filltemplate.html", form=template_to_form(template.contents, patient),
            patient=patient, template=template, date_form=date_form(dt.now(),1,1),
            time_form=time_form(dt.now()))



@app.route('/fillform/<tid>/<pid>', methods=['GET', 'POST'])            # заполнить одноразовый бланк
@login_required
def fillform(tid=0, pid=0):
    template = Template.get(id=tid)
    patient = Patient.get(id=pid)
    return render_template_string(template.contents, patient=patient, datetime=dt.now())



def yn(data, s, default=''):                 # get data from dict without errors ('' in case of no data)
    if s in data: return data[s]
    return default

def template_to_form(template, patient=patient, datajson='{}'):
    form = []
    fields= []
    datafields = []
    catchdata=0
    if datajson=='': datajson='{}'
    data = json.loads(datajson)

    f_hidden='<input type="hidden" name="{name}" value="{value}">{visible}'
    f_radio ='&nbsp;<label><input type="radio" {checked} name="{name}" value="{value}" ondblclick="this.checked=false">&nbsp;{visible}</label>'
    f_checkbox ='&nbsp;<label><input type="checkbox" {checked} name="{name}" value="{value}">&nbsp;{visible}</label>'
    f_option = '&nbsp;<option value="{value}">{visible}</option>'
    f_firstoption = '<select name="{name}">\r\n&nbsp;<option value="{value}">{visible}</option>'
    f_text = '&nbsp;<input type="text" name="{name}" value="{value}" size={size}>'
    f_textarea = '<br><textarea name="{name}" rows={rows} style="width:100%">{value}</textarea>'
    f_nondisplayed="""<h4 onclick="showhide('{id}')" style="color:blue;"><span id="{id}s">&#9205;</span> {title}</h4><span id="{id}" style="border-left-style: solid;border-left-color:blue;padding-left:1em;display:none;">"""

    last = 'b'  # первая буква последней строки
    i = 0
    k = 0
    upload = 0
    titles=1
    catchdata=0
    lines = template.split('\n')
    for linea in lines:
        k=i
        line = linea+' '
        if line[0]==' ' : line='_'
        line=line.strip()
        if line=='': line='_'


        if last=='\\' and line[0]!='\\':
            form.append('</select>')    # закрыть набор select если предыдущая строка была опцией, а дальшей нет


        if line[0]=='p':
            form.append(f_hidden.format(name='item'+str(i), value='p'*len(line), visible='<br>'*len(line)))
        elif line[0]=='_':
            form.append('<br>'*len(line))
        elif line[0] == '@':                                                                # поля данных
            string=''
            if line[1:]=='patientname': string = patient.name
            elif line[1:]=='patientsurname': string = patient.surname
            elif line[1:]=='patientfathername': string = patient.fathername
            elif line[1:]=='patientage': string = format_datetime(patient.dob, 'age')
            elif line[1:]=='signature': string = g.doctor.signature
            elif line[1:]=='date': string = format_datetime(dt.now(), 'datefull')
            elif line[1:]=='time': string = format_datetime(dt.now(), 'timefull')
            form.append(f_hidden.format(value = '='+string, name = 'item'+str(i), visible=string.replace('\n', '<br>')))
        elif line[0] in '][':            # открытие или закрытие группы
            form.append(f_hidden.format(value = line[0], name = 'item'+str(i), visible= line[1:]))
        elif line[0] in '>=':            # константы
            form.append(('<br>' if line[0]=='>' else '')+f_hidden.format(value = line, name = 'item'+str(i), visible= line[1:]))
        elif line[0]=='+':
            form.append(f_checkbox.format(name='item'+str(i), value=line, visible=line[1:],
                        checked=('checked' if yn(data, 'item'+str(i))==line else '')))
        elif line[0]=='-':
            if last == '-': i -= 1
            form.append(f_radio.format(name='item'+str(i), value=line, visible=line[1:],
                        checked=('checked' if yn(data, 'item'+str(i))==line else '')))
        elif line[0]=='#':
            form.append(f_text.format(name='item'+str(i), value=yn(data, 'item'+str(i)), size=len(line.split('#'))))
        elif line[0]=='$':
            try:
                form.append(f_textarea.format(name = 'item'+str(i), rows=int(line[1]), value=yn(data, 'item'+str(i))))
            except:
                form.append(f_textarea.format(name = 'item'+str(i), rows=1, value=yn(data, 'item'+str(i))))
        elif line[0]=='\\':
            if last!='\\':
                form.append(f_firstoption.format(name='item'+str(i), value=line, visible=line[1:],
                            selected=('selected' if yn(data, 'item'+str(i))==line else '')))
            else:
                form.append(f_option.format(name='item'+str(i), value=line, visible=line[1:],
                            selected=('selected' if yn(data, 'item'+str(i))==line else '')))
                i=i-1
        elif line[0]=='{':
            form.append(f_hidden.format(value = line, name = 'item'+str(i), \
                visible='<h3><a name ="tit{num}">{title}</a></h3>'.format(num=titles, title=line[1:])))
            titles+=1
        elif line[0] in ' \r':
            form.append('<br>')
        elif line[0] == '!' and catchdata==0:
            form.append(f_hidden.format(value = line, name = 'data'+str(i), visible=''))
            datafields.append('data'+str(i))
            catchdata=1
        elif line[0] == '(':
            form.append(f_nondisplayed.format(id='disp'+str(i), title=line[1:]))
        elif line[0] == ')':
            form.append('</span>')


        if line[0] in '{p\\@][>=+-#$>=':
            if k==i: fields.append('item'+str(i))
            catchdata=0
            i+=1
            last = line[0]

    form.append(f_hidden.format(name='fields', value='|'.join(fields), visible=''))
    form.append(f_hidden.format(name='datafields', value='|'.join(datafields), visible=''))
    form.append(f_hidden.format(name='patient_id', value=patient.id, visible=''))

    return '\n'.join(form)

def templatedata_to_record(datastring):  # text, date, datarecords
    try:
        data = json.loads(datastring)
    except:
        return ''
    fields = data['fields']
    datafields = data['datafields']

    raw_results=[]
    for field in fields.split('|'):
        raw_results.append(yn(data , field))
    data_results=[]
    df=0
    for datafield in datafields.split('|'):
        fieldname = yn(data, datafield)
        data_results.append([fieldname.strip(), yn(data, datafield.replace('data', 'item')).strip()])
        df+=1

    depth = [0]
    strings=[[]]
    results=''
    last=' '

    for s in raw_results:
        s=s.strip()
        if s=='': last=' ' #strings[-1].append('\n')
        elif s[0]=='p':
            strings[-1].append('<p><br></p>'*len(s))
        elif s[0]=='[':
            depth.append(0)
            strings.append([])
        elif s[0]=='>' or s[0]=='=' or s[0]=='@':
            strings[-1].append(('\n' if s[0]=='>' else '')+s[1:])
        elif s[0]=='{':
            strings[-1].append('\n\n{}\n'.format(s[1:]))
        elif s[0]=='+' or s[0]=='-':
            if last=='+' or last=='\\': strings[-1][-1]=strings[-1][-1]+' '
            strings[-1].append(s[1:]+' ')
            depth[-1]=1
        elif s[0]==']':
            if depth.pop()==0: nul = strings.pop()
            else: depth[-1]=1
        elif s[0]=='\\':
            if len(s)>1: strings[-1].append(s[1:])
        else:
            strings[-1].append(s)
            depth[-1]=1
        if s!='': last=s[0]
        else: last=' '
        last=''
    for ss in strings:
        for s in ss:
            if s!='\n': results=results+s+' '
            else: results=results+'\n'

    formatted_results = results.strip().replace('\r', '').replace(' \n', '\n').replace('\n ', '\n').replace(',\n', '.\n').replace('\n.', '\n')
    formatted_results = formatted_results.replace(',.', '.').replace('..', '.').replace(' ,', ',').replace(':,', ':')
    formatted_results = formatted_results.replace(':.', ':').replace('"', '""')

    year = int(yn(data, 'year', dt.now().year))
    month = int(yn(data, 'month', dt.now().month))
    day = int(yn(data, 'day', dt.now().day))
    hour = int(yn(data, 'hour', dt.now().hour))
    minute = int(yn(data, 'minute', dt.now().minute))
    date = dt(year=year, month=month, day=day, hour=hour, minute=minute)

    record = {}
    record['contents'] = formatted_results
    record['recorddate'] = date
    record['data']=str(data_results)
    record['html']=markdn(formatted_results.replace('\n', '  \n'))


    datarecords=[]

    for datarec in data_results:                   # внесение данных
        descriptor=datarec[0].split('|')
        if len(descriptor)>5 and datarec[1]!='':
            try:
                value = float(datarec[1].replace(',', '.'))
                low = float(descriptor[1].replace(',', '.'))
                high = float(descriptor[2].replace(',', '.'))
                text='-x-'
            except:
                value = low = high = 0
                text = datarec[1]
            try:
                low = float(descriptor[1].replace(',', '.'))
                high = float(descriptor[2].replace(',', '.'))
            except:
                low=high=0
            try:
                datarecords.append({
                    'name': descriptor[0],
                    'value': value,
                    'text': text,
                    'low': low,
                    'high': high,
                    'units': descriptor[3],
                    'sample': descriptor[4],
                    'test': descriptor[5],
                    'date': date})
            except:
                return render_template('print.html', text='Ошибка при анализе данных: '+str(data))
    record['datarecords']=datarecords

    return record

@app.route('/userconfig/', methods=['GET', 'POST'])            # настройки пользователя
@login_required
def userconfig():
    return render_template("userconfig-bi.html")



@app.route('/users')
@admin_required
def users():
    users = Doctor.select()
    return render_template('users.html', users=users)




@app.route('/login', methods=['GET', 'POST'])                                   # LOGIN Залогиниться
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nexturl = request.form['nexturl']


        docs = Doctor.select().where(Doctor.email==username)
        if docs.count()!=0:
            doc=docs.get()
            if check_password(doc.passwordhash, password):
                session['username']=username
                newsession = Session.create(whose=doc, beginning=dt.now(), end=dt.now()+tdelta(hours=1), ip=request.environ.get('HTTP_X_REAL_IP', request.remote_addr))
                session['stored']=newsession.id
        return redirect(nexturl)


    else:
        nexturl = request.args.get('nexturl', '')
        error = request.args.get('error', '')
        email = request.args.get('email', '')
        message = request.args.get('message', '')


    return render_template("login.html", error=error, nexturl=nexturl, email=email, message=message)


@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    try:
        currentsession=Session.get(id=session['stored'])
        currentsession.status = False
        currentsession.end = dt.now()
        currentsession.save()
    except:
        pass
    session.pop('username', None)
    g.doctor=None
    return redirect(url_for('index'))




@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        doc = request.form.to_dict()
        doc['name'] = doc['name'].strip()
        doc['surname'] = doc['surname'].strip()
        doc['email'] = doc['email'].strip()
        doc['active'] = 1
        if doc['email'] in app.config["admins"]: doc['privileges']='admin'
        if doc['profession'] == 'врач': doc['privileges']='physician'
        elif doc['profession'] == 'медсестра': doc['privileges']='nurse'
        elif doc['profession'] == 'лаборант': doc['privileges']='technician'
        elif doc['profession'] == 'лаборант': doc['privileges']='technician'
        else: doc['privileges']='other'

        docs = Doctor.select().where(Doctor.email==doc['email'])
        if doc['password']==doc['password1'] and docs.count()==0 and doc['code']==app.config["code_word"]:
            newdoc=Doctor.create(**doc, passwordhash = hash_password(doc['password']))
            return redirect(url_for('login', email=doc['email'], message='Вы зарегистрировались, теперь можно войти в систему.'))
        elif docs.count()>0:
            return redirect(url_for('login', email=doc['email'], message='Врач с таким электронным адресом уже зарегистрирован.'))
        elif doc['code']!=app.config["code_word"]:
            return render_template("signup.html", error='Неверное кодовое слово!')
        elif doc['password']!=doc['password1']:
            return render_template("signup.html", error='Не совпадают пароли!')
        else:
            return render_template("signup.html", error='Неизвестная ошибка!')
    return render_template("signup.html")


@app.route('/useredit', methods=['GET', 'POST'])
@login_required
def useredit():
    doc=g.doctor
    if request.method == 'POST':
        data=request.form.to_dict()
        if check_password(doc.passwordhash, data['oldpassword']):
            doc.name=data['name'].strip()
            doc.surname=data['surname'].strip()
            doc.email=data['email'].strip()
            doc.phone=data['phone'].strip()
            doc.profession=data['profession']
            doc.specialty=data['specialty']
            doc.signature=data['signature']
            doc.ward=data['ward']
            if data['password']==data['password1'] and data['password']!='':
                doc.passwordhash = hash_password(doc['password'])
            doc.save()
    return render_template('useredit.html', doc=doc)

@app.route('/userprint', methods=['GET', 'POST'])
@login_required
def userprint():
    templates=Template.select().where(Template.active)
    if request.method == 'POST':
        configdata = request.form.to_dict()
        config, new = Config.get_or_create(author=g.doctor, defaults = configdata)
        query=Config.update(**configdata).where(Config.author==g.doctor)
        query.execute()
    config_default, new = Config.get_or_create(default=True, defaults={'author':g.doctor, 'default':True})
    c_def = model_to_dict(config_default, recurse=False)
    c_def.pop('author')
    c_def.pop('id')
    config, new = Config.get_or_create(author=g.doctor.id, defaults=c_def)
    if new: config['default']=False                                                    # если это новый конфиг, то он не дефолтный образец
    return render_template('userprint.html', config=config, templates=templates)




'''    author = ForeignKeyField(Doctor, related_name='config')
    head = TextField()
    footer = TextField()
    hospital = CharField()
    ward = CharField()
    templates = TextField()
    default = BooleanField(default=False)'''


@app.route('/usertemplates', methods=['GET', 'POST'])
@login_required
def usertemplates():
    return render_template('usertemplates.html')




@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form['email']
        password = request.form['password']
        password1 = request.form['password1']
        signature = request.form['signature']
        specialty = request.form['specialty']
        phone = request.form['phone']
        name = request.form['name']
        surname = request.form['surname']

        doc = g.doctor
        if password==password1 and len(password)>6:
            doc.passwordhash = hash_password(password)
        else:
            if password=='':
                pass
            else:
                return render_template('message.html', text='Пароли не совпадают (or too short).')
        if doc.email!=username:
            if (Doctor.select().where(email==username).exists()):
                return render_template('message.html', text='Email belongs to other user.')
            
        doc.email = username
        doc.name = name
        doc.surname = surname
        doc.specialty = specialty
        doc.phone = phone
        doc.signature = signature
        doc.save()
        if session['username']!=doc.email:
            session['username']=doc.email
        return redirect(url_for('index'))
    else:
        return render_template("profile.html", doc = g.doctor)


@app.route('/patients_list', methods=['GET', 'POST'])
@login_required
def patients_list():
    patients = Patient.select().where(Patient.status==1)
    return render_template("patients.html", patients=patients)








@app.route('/lostpassword', methods=['GET', 'POST'])
def lostpassword():
#    return render_template('message.html', text='Обратитесь к администратору лично.')
    if request.method == 'POST':


        username = request.form['username']

        try:
            doc = Doctor.get(email=username)
        except:
            return redirect(url_for('lostpassword', error='Такой электронный адрес не зарегиcтрирован.'))
        tempsession=Session()
        tempsession.whose=doc
        tempsession.beginning=dt.now()
        tempsession.ip=request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

        tempsession.session_id = uuid4().hex
        tempsession.save()
        message={}
        html = '<p>Здравствуйте %s! Для входа в Эходату пройдите, пожалуйста, по ссылке: <a href="%s"> вход на сайт </a>'
        message['html'] = html % (doc.name+' '+doc.surname, url_for('lostpassword', temp=tempsession.session_id, _external=True))
        txt= 'Здравствуйте %s! Для входа в Эходату пройдите, пожалуйста, по ссылке: %s'
        message['txt'] = txt % (doc.name+' '+doc.surname, url_for('lostpassword', temp=tempsession.session_id, _external=True))


        send_email(message['txt'], message['html'], username)

        return render_template('message.html', text= 'Письмо со ссылкой для входа на сайт отправлено. Поменять пароль Вы сможете в личном профиле, когда войдете на сайт с помощью ссылки.')


    error = request.args.get('error', '')
    temp = request.args.get('temp', '')
    if temp=='':
        return render_template("lostpassword.html", error=error)
    else:
        tempsession = Session.get(session_id=temp)
        if (dt.now()-tempsession.beginning).seconds<6000:                        # срок действия присланной ссылки в секундах
            session['username']=tempsession.whose.email
            return redirect(url_for('profile'))
        else:
            return render_template('lostpassword.html', error='Ссылка устарела. Ссылка действительно 10 минут с момента отправки.')



def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('uploaded_file',
                                    filename=filename))
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <p><input type=file name=file>
         <input type=submit value=Upload>
    </form>
    '''

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    # '{}-{}-{}-{}'.format(rid, code, format_datetime(dt.now(), 'file'), secure_filename(filename))
    mode=request.args.get('m', '')
    if mode=='attach':
        splitfilename=filename.split('-')
        if len(splitfilename)>4: newfilename='-'.join(splitfilename[4:])
        else: newfilename=filename
        return send_from_directory(app.config['UPLOAD_FOLDER'],\
            filename, as_attachment=True, download_name=newfilename)
    else:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/loadattachment/<aid>')
@login_required
def load_attachment(aid):
    # '{}-{}-{}-{}'.format(rid, code, format_datetime(dt.now(), 'file'), secure_filename(filename))
    try:
        att=Attachment.get(id=aid)
    except:
        return('No such attachment')
    mode=request.args.get('m', '')
    if mode=='attach':
        filename=oldfilename(att.filename)
        return send_from_directory(app.config['UPLOAD_FOLDER'],\
            att.filename, as_attachment=True, attachment_filename=filename)
    else:
        return send_from_directory(app.config['UPLOAD_FOLDER'], att.filename)


@app.route('/deleteattachment/<aid>')
@login_required
def delete_attachment(aid):
    att=Attachment.get(id=aid)
    record=att.record
    if g.doctor.id==record.author.id:
        att.delete_instance()

    return redirect(url_for('record', rid=record.id, m='view'))


#@app.route('/')
#def hello_world():
#    return 'Hello from Flask!'



@app.route('/test/')
@admin_required
def test():
    users = Doctor.select()
    i=0
    for user in users:
        i+=1
        add_user_to_group(user, Group.get(Group.name=='Общая'))
    return '%s users added!' % i


#def email_to_group(group=None):
#    if group!=None:
#        members = [m.member for m in group.members]



@app.route('/internalrequest/<text>')
@login_required
def internalrequest(text):
    return('Проверка. Полученный текст |{}|.'.format(text)+' Запрос отправлен: {}.'.format(g.doctor.surname))
    return('Запрос пустой')


@app.route('/plainprint/<text>')
@login_required
def plainprint(text):
    return(render_template('print.html', text=text))


def send_email(txt, html, address, subj='Письмо от Эходаты'):
    with open('emails.log', 'a') as f:
        f.write(str(dt.now()))
        f.write('\n')
        f.write(address)
        f.write('\n')
        f.write(html)
        f.write('\n')
        f.write(txt)
        f.write('\n==========\n')
    msg = Message(subject = 'Восстановление пароля', sender='okhotin@tarusa-hospital.ru', recipients= [address])
    msg.body = txt
    msg.html = html
    mail.send(msg)
    return "Sent"

allowed_tags =list(bleach.ALLOWED_TAGS) + ['p', 'h1', 'h2', 'ul', 'li', 'img']
bleach.ALLOWED_ATTRIBUTES['img']=['src', 'alt', 'height', 'width']

def sanitize_html(text):
    code='''<div class="embed-responsive embed-responsive-16by9">
            <iframe class="embed-responsive-item" src="%s" allowfullscreen></iframe>
            </div>'''

    youtubes = re.findall('http[s]?://www.youtube(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
    textwithoutyoutube = re.sub('http[s]?://www.youtube(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 'YOUTUBEEMBED', text)
    textwithoutyoutube = bleach.linkify(bleach.clean(textwithoutyoutube, tags=allowed_tags))

    for youtube in youtubes:
        textwithoutyoutube = textwithoutyoutube.replace('YOUTUBEEMBED', code % youtube.replace('watch?v=', 'embed/'), 1)

    return textwithoutyoutube

app.jinja_env.filters['html'] = sanitize_html



def date_form(cur, months_before_after=30, dummy=1):                              # echodata 4.0
    input = f"""  <input id="record_date"
         name="record_date"
         type="date"
         value ="{str(cur).split(' ')[0]}"
         {'''min="{str(cur - tdelta(30*months_before_after)).split(' ')[0]}"
         max="{str(cur + tdelta(30*months_before_after)).split(' ')[0]}"''' if months_before_after!=0 else ''}
         required>"""
    return(input)

def time_form(cur):                              # echodata 4.0
    input = f"""  <input id="record_time"
         name="record_time"
         type="time"
         value ="{cur.strftime("%H:%M")}"
         required>"""
    return(input)


def date_form_old(cur, years_before, years_after):      # форма для даты, формат timedate или {'year':1978, 'month':7, 'day':18}

    
    form=['<select name="day">']
    for d in range(1,32):
        form.append('<option value="{0:02d}"{1}>{0}</option>'.format(d, ' selected="selected"' if d==cur.day else ''))
    form.append('</select>')

    months=['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа',\
           'сентября','октября','ноября','декабря']
    form.append('<select name="month">')
    for m in range(1,13):
        form.append('<option value="{0:02d}"{2}>{1}</option>'.format(m, months[m-1], ' selected="selected"' if m==cur.month else ''))
    form.append('</select>')

    form.append('<select name="year">')
    for y in range(cur.year-years_before, cur.year+years_after+1):
        form.append('<option value="{0}" {1}>{0}</option>'.format(y, ' selected="selected"' if y==cur.year else ''))
    form.append('</select>')

    return(' '.join(form))


def time_form_old(cur):      # форма для даты, формат timedate или {'hour':10, 'minute':10}
    form=['<select name="hour">']
    for h in range(0,24):
        form.append('<option value="{0:02d}"{1}>{0:02d}</option>'.format(h, ' selected="selected"' if h==cur.hour else ''))
    form.append('</select>:')

    form.append('<select name="minute">')
    for m in range(60):
        form.append('<option value="{0:02d}"{1}>{0:02d}</option>'.format(m, ' selected="selected"' if m==cur.minute else ''))
    form.append('</select>')
    return(' '.join(form))

def translit(s, to=1):
    translation={'а':'a', 'б':'b', 'в':'v', 'г':'g', 'д':'d', 'е':'e','ё':'e','ж':'zh','з':'z','и':'i',
                 'й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
                 'ф':'f','х':'h','ц':'c','ч':'ch','ь':"'",'ъ':"'",'ы':'y','э':'e','ю':'yu','я':'ya'}
    return s.translate(''.maketrans(translation))

def unique_secure_filename(filename, rid=0):    # создает уникальное и безопасное имя файла на основе исходного (добавляет спереди дату/время/случайные символы)
    letters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    code=randomchoice(letters)+randomchoice(letters)+randomchoice(letters)+randomchoice(letters)
    return secure_filename('{}-{}-{}-{}'.format(rid, code, format_datetime(dt.now(), 'file'), translit(filename.lower())))

def oldfilename(filename, mode='full'):  # returns filename without prefix, works as shortening filter for jinja
    splitfilename=filename.split('-')
    if len(splitfilename)>4: old = '-'.join(splitfilename[4:])
    else: old = filename
    if mode=='short':
        if len(old)>25:
            return old[0:20]+'...'+old[-5:]
    return old


def format_datetime(value, format='medium', relative=''):  # фильтр для формата даты-времени в шаблонах |datetime('date')
    if relative=='':
        relative=dt.now()
    if format == 'full':
        format="d MMMM y ' г., ' HH:mm"
    if format == 'datefull':
        format="d MMMM y ' г.'"
    if format == 'timefull':
        format="HH:mm"
    elif format == 'medium':
        format="dd/MM/y HH:mm"
    elif format == 'date':
        format="dd.MM.y"
    elif format == 'file':
        format="ddMMyy-HHmm"
    elif format == 'days':
        return value.days
    elif format == 'age':
        age = relativedelta(relative, value)
        ageyears = '{} {}'.format(age.years, ['лет', 'год', 'года', 'года', 'года', 'лет', 'лет', 'лет', 'лет', 'лет'][age.years%10])
        if age.years%100 in range(11,20): ageyears = '{} лет'.format(age.years)
        agemonths = '{} месяц{}'.format(age.months, ['ев', '', 'а', 'а','а','ев','ев','ев','ев','ев','ев','ев'][age.months])
        agedays = '{} д{}'.format(age.days, ['ней', 'ень', 'ня', 'ня', 'ня', 'ней', 'ней','ней','ней','ней'][age.days%10])
        if age.days in range(11,20): agedays = '{} дней'.format(age.years)
        if age.years>1:
            return ageyears
        elif age.years>0:
            return '{} {}'.format(ageyears, agemonths)
        else:
            return '{} {}'.format(agemonths, agedays)
    return babel.dates.format_datetime(value, format, locale='ru')

def markdn(text):
    return(markdown.markdown(text.replace('  \r', '<br>  \r')))

def markup(html):
    h=html2text.HTML2Text()
    return(h.handle(html))

def numofpatients(wid):
    wrd=Ward.get((Ward.id==wid) & (Ward.active))
    return len(Status.select().where((Status.ward==wrd) & (Status.status=='admitted')))

def beddays(from_d, to_d=dt(1978,7,18)):
    if to_d==dt(1978,7,18): to_d=dt.now()
    return relativedelta(dt(to_d.year, to_d.month, to_d.day), dt(from_d.year, from_d.month, from_d.day)).days

@app.route('/insertrecord', methods=['GET', 'POST'])
def insertrecord():
    if request.method == 'POST':
        content=request.json
        username = content['username']
        password = content['password']

        docs = Doctor.select().where(Doctor.email==username)
        if docs.count()!=0:
            doc=docs.get()
            if check_password(doc.passwordhash, password):
                recs=Record.delete().where((Record.recorddate==content['recorddate']) &
                                           (Record.patient==content['patient_id']) &
                                           (Record.author==doc))
                recs.execute()
                rec=Record.create(**content, created=dt.now(), modified=dt.now(), author = doc)
                return(str(content['patient_id']))
    return('Unsuccessful')


@app.route('/echoview', methods=['GET', 'POST'])
def echodata_from_echoview():
    if request.method == 'POST':
        content=request.json
        username = content['username']
        password = content['password']

        docs = Doctor.select().where(Doctor.email==username)
        if docs.count()!=0:
            doc=docs.get()
            if check_password(doc.passwordhash, password):
              auth=1
            else:
              return('No such user!')
    else: return('Not post request')
    fio, dob = content['name'], content['dob']
    ns=signletter(fio)
    if len(ns.split(' '))>3:
        surname=' '.join(ns.split(' ')[0:2]).replace(' ', '.*')
        name=ns.split(' ')[2]
        fathername=ns.split(' ')[3]
    else:
        surname=(ns+' xxx xxx').split(' ')[0]
        name=(ns+' xxx xxx').split(' ')[1]
        fathername=(ns+' xxx xxx').split(' ')[2]

    pts = Patient.select().where((Patient.surname.iregexp(surname)) &
                                     (Patient.name.iregexp(name)) &
                                     (Patient.fathername.iregexp(fathername)))
    triple=len(pts)
    if (len(pts)==0):
        pts = Patient.select().where(((Patient.surname.iregexp(surname)) &
                                     (Patient.name.iregexp(name)) |
                                         ((Patient.surname.iregexp(surname)) &
                                     (Patient.fathername.iregexp(fathername))) |
                                         ((Patient.name.iregexp(name)) &
                                     (Patient.fathername.iregexp(fathername)))))
    if (len(pts)>1):                 # if more than one match, select by DOB
        pts1 = Patient.select().where((Patient.dob==dt.strptime(dob, '%Y-%m-%d')))
        pts0=[p for p in pts if p in pts1]
        pts=pts0

    if (len(pts)==0):                 # check for latin names
        pts=Patient.select().where((Patient.name==fio+' xxx xxx'.split(' ')[1] and
                                    Patient.surname==fio.split(' ')[0]))

    fios=[[' '.join([pt.surname, pt.name, pt.fathername]), pt.dob, pt.id] for pt in pts]
    fios_dict={'n':len(fios)}
    i=0
    for f in fios:
        i+=1
        fios_dict[str(i)]={'fio':f[0], 'dob':str(f[1]), 'id':f[2]}
    return json.dumps(fios_dict)



app.jinja_env.filters['relativedelta'] = relativedelta

app.jinja_env.filters['beddays'] = beddays # число койко-дней (по датам, а не по времени)

app.jinja_env.filters['numofpatients'] = numofpatients

app.jinja_env.filters['datetime'] = format_datetime
# Use:
# {{ car.date_of_manufacture|datetime }}
# {{ car.date_of_manufacture|datetime('full') }}

app.jinja_env.filters['markup'] = markup

app.jinja_env.filters['oldfilename'] = oldfilename

app.jinja_env.filters['translate'] = translate

app.jinja_env.filters['dicom_translate'] = dicom_translate


app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'QAZWSXWCFEVRGBTYHNTBGRVCFE')
