from pathlib import Path
import logging.config
import zipfile
from datetime import date

import flask

from src.participant import RedcapParticipant
from src.mylogging import DEFAULT_LOGGING
from src.executor import executor
from src.constants import DOWNLOAD_DIR
from src.event_generator import EventGenerator

bp = flask.Blueprint('blueprints', __name__)
auto_bp = flask.Blueprint('auto_bp', __name__)
if not Path(DOWNLOAD_DIR).exists():
    Path(DOWNLOAD_DIR).mkdir()

logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)


def done(fn):
    if fn.cancelled():
        logger.info('Operation cancelled')
    elif fn.done():
        error = fn.exception()
        if error:
            logger.error('Error returned: {}'.format(error))
        else:
            result = fn.result()
            if result:
                logger.info(result)


# get subject object from id in form
def get_subject():
    subject_id = flask.request.form['participant']
    if len(subject_id) != 6 or not subject_id.startswith('ASH'):
        logger.warning(f'Warning: {subject_id} is not in the form \"ASHnnn\"')

    return subject_id


@bp.route('/diary1', methods=['POST'])
def diary1():
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        m = eg.daily_diary_one()

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.info(m)
    return 'success'


@bp.route('/diary3', methods=['POST'])
def diary2():
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        m = eg.daily_diary_three()

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.info(m)
    return 'success'


@bp.route('/messages', methods=['POST'])
def generate_messages():
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        future_response = executor.submit(eg.generate_messages)
        future_response.add_done_callback(done)
    except Exception as err:
        logger.error(str(err))
        return str(err)

    status = f'Message generation started for {subject}'
    logger.info(status)
    return status


@bp.route('/delete', methods=['POST'])
def delete_events():
    # Access form properties, get subject information, get events, and delete
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        future_response = executor.submit(eg.delete_messages)
        future_response.add_done_callback(done)
    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Message deletion started for {subject}'
    logger.info(status)

    return status


@bp.route('/task', methods=['POST'])
def task():
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        m = eg.generate_task_files()

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.info(m)
    return m


@bp.route('/responses', methods=['POST'])
def responses():
    subject = get_subject()
    if not subject:
        return 'none'
    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        future_response = executor.submit(eg.get_conversations)
        future_response.add_done_callback(done)

    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Retrieving conversations for {subject}'
    logger.info(status)
    return status


def isisoformat(item):
    try:
        date.fromisoformat(item)
    except ValueError:
        return False
    return True


@bp.route('/progress', methods=['GET'])
def progress():
    logfile = DEFAULT_LOGGING['handlers']['rotating_file']['filename']
    with open(logfile, 'r') as f:
        lines = f.readlines()

    daily_messages = [x.split('  ')[-1] for x in reversed(lines)
                      if isisoformat(x.split()[0]) and date.fromisoformat(x.split()[0]) == date.today()]

    return flask.render_template('progress.html', messages=daily_messages)


@bp.route('/')
def index():
    return flask.render_template('index.html')


@bp.route('/validate', methods=['POST'])
def validate():
    subject = get_subject()
    try:
        redcap_participant = RedcapParticipant(subject,
                                               flask.current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
        logger.info(f'{subject} found in RedCap')
        sessions = dict(s0='Session 0',
                        s1='Session 1')
        for key in sessions:
            if key in redcap_participant.redcap:
                logger.info(f'{sessions[key]} found')
            else:
                logger.info(f'{sessions[key]} not found')
        return subject

    except Exception as err:
        logger.error(str(err))
        return 'invalid'


@bp.route('/files', methods=['POST'])
def download_files():
    subject = get_subject()
    if not subject:
        return 'none'
    csv_path = Path(DOWNLOAD_DIR)
    files = csv_path.glob(f'*{subject}*.*')
    compression = zipfile.ZIP_STORED
    archive_name = f'{subject}.zip'
    with zipfile.ZipFile(Path.home() / archive_name, mode='w', compression=compression) as zf:
        for f in files:
            zf.write(f, arcname=f.name, compress_type=compression)
    return flask.send_from_directory(Path.home(), archive_name, as_attachment=True)


@bp.route('/update', methods=['POST'])
def update():
    subject = get_subject()
    if not subject:
        return 'none'
    try:
        eg = EventGenerator(config=flask.current_app.config['AUTOMATIONCONFIG'],
                            participant_id=subject,
                            instance_path=Path(flask.current_app.instance_path))
        future_response = executor.submit(eg.update_contact)
        future_response.add_done_callback(done)

    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Updating messages for {subject}'
    logger.info(status)
    return status
