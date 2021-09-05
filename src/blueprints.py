from datetime import datetime
from typing import Optional, List

from flask import (
    Blueprint, current_app, flash, make_response, render_template, request, send_file
)
from flask.json import jsonify
from werkzeug.datastructures import ImmutableMultiDict

from src.apptoto import Apptoto, ApptotoError
from src.event_generator import EventGenerator
from src.redcap import Redcap, RedcapError
from src.participant import Participant
from src.progress_log import print_progress

import threading

bp = Blueprint('blueprints', __name__)


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


def generate_messages_threaded(event_generator):
    try:
        event_generator.generate()
        print_progress('message generation complete')
        filename = event_generator.write_file()
        print_progress('wrote file {}'.format(filename))

    except ApptotoError as err:
        print_progress(str(err))

    except Exception as err:
        print_progress(str(err))


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

            x = threading.Thread(target=generate_messages_threaded, args=(eg,))
            x.start()

            flash('Message generation started for {}'.format(participant.participant_id))

            return render_template('generation_form.html')


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
            x = threading.Thread(target=delete_events_threaded, args=(apptoto, participant,))
            x.start()

            flash('Message deletion started for {}'.format(participant.participant_id))

            return render_template('delete_form.html')


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
