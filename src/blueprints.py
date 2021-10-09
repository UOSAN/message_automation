from typing import Optional, List
from pathlib import Path
from collections import deque
import logging.config

from flask import (
    Blueprint, current_app, flash, make_response, render_template, request, redirect, url_for
)

from flask.json import jsonify
from flask_autoindex import AutoIndexBlueprint
from werkzeug.datastructures import ImmutableMultiDict

import src.event_generator as eg
from src.redcap import Redcap, RedcapError
from src.logging import DEFAULT_LOGGING
from src.executor import executor
from src.constants import DOWNLOAD_DIR

bp = Blueprint('blueprints', __name__)
auto_bp = Blueprint('auto_bp', __name__)
if not Path(DOWNLOAD_DIR).exists():
    Path(DOWNLOAD_DIR).mkdir()
AutoIndexBlueprint(auto_bp, browse_root=DOWNLOAD_DIR)
future_keys = []
done_messages = deque(maxlen=200)
logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)


def done(fn):
    if fn.cancelled():
        logger.info('cancelled')
    elif fn.done():
        error = fn.exception()
        if error:
            logger.info('error returned: {}'.format(error))
        else:
            result = fn.result()
            if result:
                logger.info(result)


def _validate_participant_id(form_data: ImmutableMultiDict) -> Optional[List[str]]:
    errors = []
    if len(form_data['participant']) != 6 or not form_data['participant'].startswith('ASH'):
        errors.append('Participant identifier must be in form \"ASHnnn\"')

    if errors:
        return errors
    else:
        return None


def diary(particpant_id):
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
            eg.daily_diary(config=current_app.config['AUTOMATIONCONFIG'], participant=participant)

        except Exception as err:
            flash(str(err), 'danger')
            return redirect(url_for('blueprints.diary_form'))

        flash('diary messages created')
        return redirect(url_for('blueprints.diary_form'))

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
                eg.daily_diary(config=current_app.config['AUTOMATIONCONFIG'], participant=participant)

            except Exception as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.diary_form'))

            flash('diary messages created')
            return redirect(url_for('blueprints.diary_form'))


@bp.route('/generate', methods=['GET', 'POST'])
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
                return redirect(url_for('blueprints.generation_form'))

            rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
            try:
                participant = rc.get_participant(request.form['participant'])
            except Exception as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.generation_form'))

            key = ('generate {}'.format(participant.participant_id))

            try:
                future_response = executor.submit_stored(key, eg.generate_messages,
                                                         config=current_app.config['AUTOMATIONCONFIG'],
                                                         participant=participant,
                                                         instance_path=current_app.instance_path)
                future_response.add_done_callback(done)
                future_keys.append(key)
            except Exception as err:
                flash(str(err), 'danger')
                return redirect(url_for('blueprints.generation_form'))

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

            key = ('delete {}'.format(participant.participant_id))

            try:
                future_response = executor.submit_stored(key, eg.delete_messages,
                                                         config=current_app.config['AUTOMATIONCONFIG'],
                                                         participant=participant)
                future_response.add_done_callback(done)
                future_keys.append(key)
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
                m = eg.generate_task_files(config=current_app.config['AUTOMATIONCONFIG'],
                                           participant=participant,
                                           instance_path=current_app.instance_path)

            except Exception as err:
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

    try:
        conversations = eg.get_conversations(config=current_app.config['AUTOMATIONCONFIG'], participant=participant)
    except Exception as err:
        flash(str(err), 'danger')
        return make_response((jsonify(str(err)), 404))

    return make_response(jsonify(conversations), 200)


@bp.route('/progress', methods=['GET'])
def progress():
    messages = list(done_messages)
    finished = [k for k in future_keys if executor.futures.done(k)]

    for key in future_keys:
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
        future_keys.remove(key)

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


# this worked, can't figure out why it won't work now
@bp.route('/everything', methods=['GET', 'POST'])
def everything():
    if request.method == 'GET':
        return render_template('everything.html')

    elif request.method == 'POST':
        if 'download' in request.form:
            flash('download')
            return redirect(url_for('blueprints.cleanup'))

        elif 'messages' in request.form:
            flash('generate messages')
            return redirect(url_for('blueprints.cleanup'))

        elif 'task' in request.form:
            flash('generate task messages')
            return redirect(url_for('blueprints.cleanup'))

        elif 'diary' in request.form:
            flash('diary')
            return redirect(url_for('blueprints.cleanup'))

        elif 'conversations' in request.form:
            flash('count things')
            return redirect(url_for('blueprints.cleanup'))

        elif 'delete' in request.form:
            flash('delete messages')
            return redirect(url_for('blueprints.everything'))


@bp.route('/', methods=['GET', 'POST'])
def message_automation():
    if request.method == 'GET':
        return render_template('main_page.html')

    elif request.method == 'POST':
        if 'download' in request.form:
            return redirect('/downloads')

        # everything else uses the participant id

        error = _validate_participant_id(request.form)
        if error:
            for e in error:
                flash(e, 'danger')
            return redirect(url_for('blueprints.message_automation'))

        rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
        try:
            participant = rc.get_participant(request.form['participant'])
        except RedcapError as err:
            flash(str(err), 'danger')
            return redirect(url_for('blueprints.message_automation'))

        if 'messages' in request.form:
            flash('generate messages')
            return redirect(url_for('blueprints.message_automation'))

        if 'task' in request.form:
            flash('generate task messages')
            return redirect(url_for('blueprints.message_automation'))

        if 'diary' in request.form:
            flash('diary')
            return redirect(url_for('blueprints.message_automation'))

        if 'conversations' in request.form:
            flash('count things')
            return redirect(url_for('blueprints.message_automation'))

        if 'delete' in request.form:
            flash('delete messages')
            return redirect(url_for('blueprints.message_automation'))
        

        



