from datetime import datetime
from typing import Optional, List
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, make_response, render_template, request, redirect, url_for
)

from flask.json import jsonify
from flask_autoindex import AutoIndexBlueprint
from werkzeug.datastructures import ImmutableMultiDict

from src.apptoto import Apptoto, ApptotoError
from src.event_generator import daily_diary, generate_messages, generate_task_files
from src.redcap import Redcap, RedcapError
from src.progress_log import print_progress
from src.executor import executor
from src.constants import DOWNLOAD_DIR

bp = Blueprint('blueprints', __name__)

auto_bp = Blueprint('auto_bp', __name__)

if not Path(DOWNLOAD_DIR).exists():
    Path(DOWNLOAD_DIR).mkdir()

AutoIndexBlueprint(auto_bp, browse_root=DOWNLOAD_DIR)

futurekeys = []
# todo replace with ring buffer
done_messages = []


def delete_events_threaded(apptoto, participant):
    print_progress('Deletion started for {}'.format(participant.participant_id))
    begin = datetime.now()
    event_ids = apptoto.get_messages(begin=begin, participant=participant)
    deleted = 0
    for event_id in event_ids:
        apptoto.delete_event(event_id)
        deleted += 1
        print_progress('Deleted event {}, {} of {}'.format(event_id, deleted, len(event_ids)))

    print_progress('Deleted {} messages for {}.'.format(len(event_ids), participant.participant_id))


def done(fn):
    if fn.cancelled():
        print_progress('cancelled')
    elif fn.done():
        error = fn.exception()
        if error:
            print_progress('error returned: {}'.format(error))
        else:
            result = fn.result()
            if result:
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
                return redirect(url_for('blueprints.diary_form'))

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                participant = rc.get_participant(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.diary_form'))

            try:
                daily_diary(config=current_app.config['AUTOMATIONCONFIG'], participant=participant)

            except ApptotoError as err:
                flash(str(err), 'danger')

            flash('diary messages created')
            return redirect(url_for('blueprints.diary_form'))


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
                redirect(url_for('blueprints.generation_form'))

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                participant = rc.get_participant(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                redirect(url_for('blueprints.generation_form'))

            key = ('generate {}'.format(participant.participant_id))

            try:
                future_response = executor.submit_stored(key, generate_messages,
                                                         config=current_app.config['AUTOMATIONCONFIG'],
                                                         participant=participant,
                                                         instance_path=current_app.instance_path)
                future_response.add_done_callback(done)
                futurekeys.append(key)
            except ValueError as err:
                flash(str(err), 'danger')
                redirect(url_for('blueprints.generation_form'))

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
                return redirect(url_for('blueprints.delete_events'))

            apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                              user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])

            key = ('delete {}'.format(participant.participant_id))

            try:
                future_response = executor.submit_stored(key, delete_events_threaded, apptoto, participant)
                future_response.add_done_callback(done)
                futurekeys.append(key)
            except ValueError as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.delete_events'))

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
                return redirect(url_for('blueprints.task'))

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                participant = rc.get_participant(request.form['participant'])
            except RedcapError as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.task'))

            try:
                m = generate_task_files(config=current_app.config['AUTOMATIONCONFIG'],
                                        participant=participant,
                                        instance_path=current_app.instance_path)

            except ApptotoError as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.task'))

            flash(m)
            return redirect(url_for('blueprints.task'))


@bp.route('/count/<participant_id>', methods=['GET'])
def participant_responses(participant_id):
    part = ImmutableMultiDict({'participant': participant_id})
    error = _validate_participant_id(part)
    if error:
        return make_response((jsonify(error), 400))

    # Use participant ID to get phone number, then get all events and filter conversations for participant responses.
    rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])

    try:
        participant = rc.get_participant(participant_id)

    except RedcapError as err:
        return make_response((jsonify(str(err)), 404))

    apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                      user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])

    try:
        conversations = apptoto.get_responses(participant)
    except ApptotoError as err:
        flash(str(err), 'danger')
        return make_response((jsonify(str(err)), 404))

    return make_response(jsonify(conversations), 200)


@bp.route('/progress', methods=['GET'])
def progress():
    messages = list(done_messages)
    finished = [k for k in futurekeys if executor.futures.done(k)]

    for key in futurekeys:
        if executor.futures.running(key):
            msg = '{} running'.format(key)
            messages.append(msg)
        elif executor.futures.done(key):
            if executor.futures.exception(key):
                msg = '{} error: {}'.format(key, executor.futures.exception(key))
            elif executor.futures.cancelled(key):
                msg = '{} cancelled'.format(key)
            else:
                msg = '{} finished'.format(key)

            messages.append(msg)
            done_messages.append(msg)

    for key in finished:
        executor.futures.pop(key)
        futurekeys.remove(key)

    return render_template('progress.html', messages=messages)


@bp.route('/cleanup', methods=['GET', 'POST'])
def cleanup():
    if request.method == 'GET':
        return render_template('cleanup_form.html')
    elif request.method == 'POST':
        if 'submit' in request.form:
            csv_path = Path(DOWNLOAD_DIR)
            csvfiles = csv_path.glob('*.csv')
            for filename in csvfiles:
                filename.unlink()

            flash('Deleted all csv files in download folder')
        return redirect(url_for('blueprints.cleanup'))


@bp.route('/everything', methods=['GET', 'POST'])
def everything():
    if request.method == 'GET':
        return render_template('everything.html')

    elif request.method == 'POST':
        if 'generate' in request.form:
            flash('generate messages')
            return redirect(url_for('blueprints.everything'))

        elif 'task' in request.form:
            flash('generate task messages')
            return redirect(url_for('blueprints.everything'))

        elif 'diary' in request.form:
            flash('diary')
            return redirect(url_for('blueprints.everything'))

        elif 'count' in request.form:
            flash('count things')
            return redirect(url_for('blueprints.everything'))

        elif 'delete' in request.form:
            flash('delete messages')
            return redirect(url_for('blueprints.everything'))

        elif 'download' in request.form:
            flash('download messages')
            return redirect(url_for('blueprints.everything'))
