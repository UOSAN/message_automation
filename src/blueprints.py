from datetime import datetime
from typing import Optional, List

from flask import (
    Blueprint, current_app, flash, make_response, render_template, request, send_file
)
from flask.json import jsonify
from werkzeug.datastructures import ImmutableMultiDict

from src.apptoto import Apptoto
from src.event_generator import EventGenerator
from src.redcap import Redcap, RedcapError, logSomething

bp = Blueprint('blueprints', __name__)



def logFunction(func):
    fname = func.__name__
    def logfunc(*args, **kwargs):
        logSomething(fname)
        return func(*args, **kwargs)
    return logfunc


@logFunction
def _validate_participant_id(form_data: ImmutableMultiDict) -> Optional[List[str]]:
    errors = []
    if len(form_data['participant']) != 6 or not form_data['participant'].startswith('ASH'):
        errors.append('Participant identifier must be in form \"ASHnnn\"')

    if errors:
        return errors
    else:
        return None

@logFunction
@bp.route('/diary', methods=['GET', 'POST'])
def diary_form():
    if request.method == 'GET':
        return render_template('daily_diary_form.html')
    elif request.method == 'POST':
        if 'submit' in request.form:
            # Access form properties and do stuff
            error = _validate_participant_id(request.form)
            if error:
                for e in error:
                    flash(e, 'danger')
                return render_template('daily_diary_form.html')

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                part = rc.get_session_0(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('daily_diary_form.html')

            eg = EventGenerator(config=current_app.config['AUTOMATIONCONFIG'], participant=part,
                                instance_path=current_app.instance_path)
            if not eg.daily_diary():
                flash('Failed to create daily diary round 1', 'danger')
            return render_template('daily_diary_form.html')

@logFunction
@bp.route('/', methods=['GET', 'POST'])
def generation_form():
    if request.method == 'GET':
        return render_template('generation_form.html')
    elif request.method == 'POST':
        if 'submit' in request.form:
            # Access form properties and do stuff
            error = _validate_participant_id(request.form)
            if error:
                for e in error:
                    flash(e, 'danger')
                return render_template('generation_form.html')

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                part = rc.get_participant_specific_data(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('generation_form.html')

            eg = EventGenerator(config=current_app.config['AUTOMATIONCONFIG'], participant=part,
                                instance_path=current_app.instance_path)
            if eg.generate():
                f = eg.write_file()
                return send_file(f, mimetype='text/csv', as_attachment=True)
            else:
                flash('Failed to create some messages', 'danger')
            return render_template('generation_form.html')

@logFunction
@bp.route('/delete', methods=['GET', 'POST'])
def delete_events():
    if request.method == 'GET':
        logSomething('get')
        return render_template('delete_form.html')
    elif request.method == 'POST':
        logSomething('post')
        if 'submit' in request.form:
            # Access form properties, get participant information, get events, and delete
            participant_id = request.form['participant']
            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])

            try:
                phone_number = rc.get_participant_phone(participant_id)
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('delete_form.html')

            apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                              user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])

            begin = datetime.now()
            event_ids = apptoto.get_events(begin=begin, phone_number=phone_number)
            for event_id in event_ids:
                apptoto.delete_event(event_id)

            flash('Deleted messages', 'success')
            return render_template('delete_form.html')

@logFunction
@bp.route('/task', methods=['GET', 'POST'])
def task():
    if request.method == 'GET':
        return render_template('task_form.html')
    elif request.method == 'POST':
        if 'value-task' in request.form:
            error = _validate_participant_id(request.form)
            if error:
                for e in error:
                    flash(e, 'danger')
                return render_template('task_form.html')

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                part = rc.get_participant_specific_data(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('task_form.html')

            eg = EventGenerator(config=current_app.config['AUTOMATIONCONFIG'], participant=part,
                                instance_path=current_app.instance_path)

            f = eg.task_input_file()
            return send_file(f, mimetype='text/csv', as_attachment=True)

@logFunction
@bp.route('/count/<participant_id>', methods=['GET'])
def participant_responses(participant_id):
    part = ImmutableMultiDict({'participant': participant_id})
    error = _validate_participant_id(part)
    if error:
        return make_response((jsonify(error), 400))

    # Use participant ID to get phone number, then get all events and filter conversations for participant responses.
    rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])

    try:
        phone_number = rc.get_participant_phone(participant_id)
    except RedcapError as err:
        return make_response((jsonify(str(err)), 404))

    apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                      user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])

    conversations = apptoto.get_conversations(phone_number=phone_number)
    return make_response(jsonify(conversations), 200)
