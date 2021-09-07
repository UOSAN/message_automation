from datetime import datetime
from typing import Optional, List

from flask import (
    Blueprint, current_app, flash, make_response, render_template, request, send_file, redirect, url_for
)

from flask.json import jsonify
from werkzeug.datastructures import ImmutableMultiDict

from src.apptoto import Apptoto, ApptotoError
from src.event_generator import EventGenerator
from src.redcap import Redcap, RedcapError
from src.participant import Participant
from src.progress_log import print_progress
from src.executor import executor

bp = Blueprint('blueprints', __name__)
futurekeys = []


def delete_events_threaded(apptoto, participant):
    print_progress('Deletion started for {}'.format(participant.participant_id))
    begin = datetime.now()
    event_ids = apptoto.get_events(begin=begin, participant=participant)
    print_progress('Found {} messages total'.format(len(event_ids)))

    deleted = 0
    try:
        for event_id in event_ids:
            apptoto.delete_event(event_id)
            deleted += 1
            print_progress('Deleted event {}, {} of {}'.format(event_id, deleted, len(event_ids)))

        print_progress('Deleted {} messages for {}.'.format(len(event_ids), participant.participant_id))

    except ApptotoError as err:
        print_progress(str(err))

    return 'Deletion complete'


def generate_messages_threaded(event_generator):
    try:
        event_generator.generate()
        print_progress('message generation complete')

    except ApptotoError as err:
        print_progress(str(err))

    try:
        filename = event_generator.write_file()
        print_progress('wrote file {}'.format(filename))
    #    send_file(filename, mimetype='text/csv', as_attachment=True)
    except Exception as err:
        print_progress(str(err))

    return 'Message generation complete'


# will need some work, mainly for testing right now
def done(fn):
    if fn.cancelled():
        print_progress('cancelled')
    elif fn.done():
        error = fn.exception()
        if error:
            print_progress('error returned: {}'.format(error))
        else:
            result = fn.result()
            print_progress(result)


def _validate_participant_id(form_data: ImmutableMultiDict) -> Optional[List[str]]:
    errors = []
    if len(form_data['participant']) != 6 or not form_data['participant'].startswith('ASH'):
        errors.append('Participant identifier must be in form \"ASHnnn\"')

    if errors:
        return errors
    else:
        return None


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
                part = rc.get_participant(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('daily_diary_form.html')

            eg = EventGenerator(config=current_app.config['AUTOMATIONCONFIG'], participant=part,
                                instance_path=current_app.instance_path)
            try:
                eg.daily_diary()

            except ApptotoError as err:
                flash(str(err), 'danger')

            return render_template('daily_diary_form.html')


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
                participant = rc.get_participant(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('generation_form.html')

            eg = EventGenerator(config=current_app.config['AUTOMATIONCONFIG'], participant=participant,
                                instance_path=current_app.instance_path)

            key = ('generate {}'.format(participant.participant_id))

            try:
                future_response = executor.submit_stored(key, generate_messages_threaded, eg)
                future_response.add_done_callback(done)
                futurekeys.append(key)
            except ValueError as err:
                flash(str(err), 'danger')

            flash('Message generation started for {}'.format(participant.participant_id))

            return redirect(url_for('blueprints.generation_form'))


@bp.route('/delete', methods=['GET', 'POST'])
def delete_events():
    if request.method == 'GET':
        return render_template('delete_form.html')

    elif request.method == 'POST':
        if 'submit' in request.form:
            # Access form properties, get participant information, get events, and delete
            participant_id = request.form['participant']

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])

            try:
                participant = rc.get_participant(participant_id)
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('delete_form.html')

            apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                              user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])

            key = ('delete {}'.format(participant.participant_id))

            try:
                future_response = executor.submit_stored(key, delete_events_threaded, apptoto, participant)
                future_response.add_done_callback(done)
                futurekeys.append(key)
            except ValueError as err:
                flash(str(err), 'danger')

            flash('Message deletion started for {}'.format(participant.participant_id))

            return redirect(url_for('blueprints.delete_events'))


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
                part = rc.get_participant(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return render_template('task_form.html')

            eg = EventGenerator(config=current_app.config['AUTOMATIONCONFIG'], participant=part,
                                instance_path=current_app.instance_path)

            try:
                f = eg.task_input_file()

            except ApptotoError as err:
                flash(str(err), 'danger')
                return render_template('task_form.html')

            return send_file(f, mimetype='text/csv', as_attachment=True)


@bp.route('/count/<participant_id>', methods=['GET'])
def participant_responses(participant_id):
    part = ImmutableMultiDict({'participant': participant_id})
    error = _validate_participant_id(part)
    if error:
        return make_response((jsonify(error), 400))

    # Use participant ID to get phone number, then get all events and filter conversations for participant responses.
    rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])

    try:
        phone_number = rc.get_participant(participant_id).phone_number

    except RedcapError as err:
        return make_response((jsonify(str(err)), 404))

    apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                      user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])

    try:
        conversations = apptoto.get_conversations(phone_number=phone_number)
    except ApptotoError as err:
        flash(str(err), 'danger')
        return make_response((jsonify(str(err)), 404))

    return make_response(jsonify(conversations), 200)


@bp.route('/progress')
def progress():
    messages = []
    for key in futurekeys:
        messages.append({'action': key, 'status': executor.futures._state(key)})

    finished = [k for k in futurekeys if executor.futures.done(k)]

    for key in finished:
        executor.futures.pop(key)
        futurekeys.remove(key)

    return jsonify(messages)
