from pathlib import Path
from collections import deque
import logging.config
import zipfile
from datetime import date

import flask
from flask_autoindex import AutoIndexBlueprint

import src.event_generator as eg
from src.redcap import Redcap, RedcapError
from src.logging import DEFAULT_LOGGING
from src.executor import executor
from src.constants import DOWNLOAD_DIR

bp = flask.Blueprint('blueprints', __name__)
auto_bp = flask.Blueprint('auto_bp', __name__)
if not Path(DOWNLOAD_DIR).exists():
    Path(DOWNLOAD_DIR).mkdir()
AutoIndexBlueprint(auto_bp, browse_root=DOWNLOAD_DIR)


logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)


def done(fn):
    if fn.cancelled():
        logger.critical('Operation cancelled')
    elif fn.done():
        error = fn.exception()
        if error:
            logger.error('Error returned: {}'.format(error))
        else:
            result = fn.result()
            if result:
                logger.critical(result)
                status_messages.append(result)


# get participant object from id in form
def get_participant():
    participant_id = flask.request.form['participant']
    if len(participant_id) != 6 or not participant_id.startswith('ASH'):
        status_messages.append(f'Warning: {participant_id} is not in the form \"ASHnnn\"')

    rc = Redcap(api_token=flask.current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
    try:
        participant = rc.get_participant(participant_id)
    except RedcapError as err:
        status_messages.append(str(err))
        return None
    return participant


@bp.route('/diary', methods=['POST'])
def diary():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        m = eg.daily_diary(config=flask.current_app.config['AUTOMATIONCONFIG'], participant=participant)

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.critical(m)
    return 'success'


@bp.route('/messages', methods=['POST'])
def generate_messages():
    participant = get_participant()
    if not participant:
        return 'none'

    key = ('generate {}'.format(participant.participant_id))

    try:
        future_response = executor.submit_stored(key, eg.generate_messages,
                                                 config=flask.current_app.config['AUTOMATIONCONFIG'],
                                                 participant=participant,
                                                 instance_path=flask.current_app.instance_path)
        future_response.add_done_callback(done)
    except Exception as err:
        logger.error(str(err))
        return str(err)

    status = f'Message generation started for {participant.participant_id}'
    logger.critical(status)
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
                                                 config=flask.current_app.config['AUTOMATIONCONFIG'],
                                                 participant=participant)
        future_response.add_done_callback(done)
    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Message deletion started for {participant.participant_id}'
    logger.critical(status)

    return status


@bp.route('/task', methods=['POST'])
def task():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        m = eg.generate_task_files(config=flask.current_app.config['AUTOMATIONCONFIG'],
                                   participant=participant,
                                   instance_path=flask.current_app.instance_path)

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.critical(m)
    return m


@bp.route('/responses', methods=['POST'])
def responses():
    participant = get_participant()
    if not participant:
        return 'none'

    key = ('conversations {}'.format(participant.participant_id))

    try:
        future_response = executor.submit_stored(key, eg.get_conversations,
                                                 config=flask.current_app.config['AUTOMATIONCONFIG'],
                                                 participant=participant,
                                                 instance_path=flask.current_app.instance_path)
        future_response.add_done_callback(done)

    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Retrieving conversations for {participant.participant_id}'
    logger.critical(status)
    return status


@bp.route('/progress', methods=['GET'])
def progress():
    logfile = DEFAULT_LOGGING['handlers']['rotating_file']['filename']
    with open(logfile, 'r') as f:
        lines = f.readlines()
    daily_messages = [x.split('  ')[-1] for x in lines
                      if date.fromisoformat(x.split()[0]) == date.today()]

    return flask.render_template('progress.html', messages=daily_messages)



@bp.route('/cleanup', methods=['GET', 'POST'])
def cleanup():
    if flask.request.method == 'GET':
        return flask.render_template('cleanup_form.html')
    elif flask.request.method == 'POST':
        if 'submit' in flask.request.form:
            csv_path = Path(DOWNLOAD_DIR)
            csvfiles = csv_path.glob('*.csv')
            for filename in csvfiles:
                filename.unlink()

            logger.critical('Deleted all csv files in download folder')
        return flask.redirect(flask.url_for('blueprints.cleanup'))


@bp.route('/')
def index():
    return flask.render_template('index.html')


@bp.route('/validate', methods=['POST'])
def validate():
    participant = get_participant()
    if participant:
        logger.critical(f'{participant.participant_id} found in RedCap')
        if not all(vars(participant).values()):
            missing = ', '.join([x for x in vars(participant) if not vars(participant)[x]])
            logger.error(f'{participant.participant_id} is missing information: {missing}')
        return participant.participant_id
    else:
        return 'none'


@bp.route('/files', methods=['POST'])
def download_files():
    participant = get_participant()
    if not participant:
        return 'none'
    csv_path = Path(DOWNLOAD_DIR)
    csvfiles = csv_path.glob(f'*{participant.participant_id}*.csv')
    compression = zipfile.ZIP_STORED
    archive_name = f'{participant.participant_id}.zip'
    with zipfile.ZipFile(Path.home() / archive_name, mode='w', compression=compression) as zf:
        for f in csvfiles:
            zf.write(f, arcname=f.name, compress_type=compression)
    return flask.send_from_directory(Path.home(), archive_name, as_attachment=True)
