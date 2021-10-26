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

# this has evolved into the main way to show messages for the user.
# Could possibly replace/merge with logging
future_keys = []
status_messages = deque(maxlen=200)

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


# get participant object from id in form
def get_participant():
    participant_id = request.form['participant']
    if len(participant_id) != 6 or not participant_id.startswith('ASH'):
        status_messages.append(f'Warning: {participant_id} is not in the form \"ASHnnn\"')

    rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
    try:
        participant = rc.get_participant(participant_id)
    except RedcapError as err:
        status_messages.append(str(err))
        return None

    status_messages.append(f'Participant {participant_id} found in RedCap')

    return participant



@bp.route('/diary', methods=['POST'])
def diary():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        eg.daily_diary(config=current_app.config['AUTOMATIONCONFIG'], participant=participant)

    except Exception as err:
        status_messages.append(str(err))
        return str(err)

    status_messages.append(f'Diary messages created for {participant.participant_id}')
    return 'success'


@bp.route('/messages', methods=['POST'])
def generate_messages():
    participant = get_participant()
    if not participant:
        return 'none'

    key = ('generate {}'.format(participant.participant_id))

    try:
        future_response = executor.submit_stored(key, eg.generate_messages,
                                                 config=current_app.config['AUTOMATIONCONFIG'],
                                                 participant=participant,
                                                 instance_path=current_app.instance_path)
        future_response.add_done_callback(done)
        future_keys.append(key)
    except Exception as err:
        status_messages.append(str(err))
        return str(err)

    status = f'Message generation started for {participant.participant_id}'
    status_messages.append(status)
    return status


@bp.route('/delete', methods=['POST'])
def delete_events():
    # Access form properties, get participant information, get events, and delete
    participant = get_participant()
    if not participant:
        return 'none'

    key = ('delete {}'.format(participant.participant_id))

    try:
        future_response = executor.submit_stored(key, eg.delete_messages,
                                                 config=current_app.config['AUTOMATIONCONFIG'],
                                                 participant=participant)
        future_response.add_done_callback(done)
        future_keys.append(key)
    except ValueError as err:
        status_messages.append(str(err))
        return str(err)

    status = f'Message deletion started for {participant.participant_id}'
    status_messages.append(status)

    return status


@bp.route('/task', methods=['POST'])
def task():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        m = eg.generate_task_files(config=current_app.config['AUTOMATIONCONFIG'],
                                   participant=participant,
                                   instance_path=current_app.instance_path)

    except Exception as err:
        status_messages.append(str(err))
        return str(err)

    status_messages.append(m)
    return m


@bp.route('/count/<participant_id>', methods=['GET'])
def participant_responses(participant_id):
    part = ImmutableMultiDict({'participant': participant_id})

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


@bp.route('/responses', methods=['POST'])
def responses():
    participant = get_participant()
    if not participant:
        return 'no participant'
    status_messages.append(participant.participant_id)
    return 'ok'


@bp.route('/progress', methods=['GET'])
def progress():
    messages = list(status_messages)
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
            status_messages.append(msg)

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


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/validate', methods=['POST'])
def validate():
    participant = get_participant()
    if participant:
        return participant.participant_id
    else:
        return 'none'
