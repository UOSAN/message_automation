from pathlib import Path
import logging.config
import zipfile
from datetime import date

import flask

import src.event_generator as eg
from src.participant import Subject
from src.mylogging import DEFAULT_LOGGING
from src.executor import executor
from src.constants import DOWNLOAD_DIR

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

    try:
        subject = Subject(subject_id, flask.current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
    except Exception as err:
        logger.error(str(err))
        return None
    return subject


@bp.route('/diary1', methods=['POST'])
def diary1():
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        m = eg.daily_diary_one(config=flask.current_app.config['AUTOMATIONCONFIG'], subject=subject)

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
        m = eg.daily_diary_three(config=flask.current_app.config['AUTOMATIONCONFIG'], subject=subject)

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
        future_response = executor.submit(eg.generate_messages,
                                          config=flask.current_app.config['AUTOMATIONCONFIG'],
                                          subject=subject,
                                          instance_path=flask.current_app.instance_path)
        future_response.add_done_callback(done)
    except Exception as err:
        logger.error(str(err))
        return str(err)

    status = f'Message generation started for {subject.id}'
    logger.info(status)
    return status


@bp.route('/delete', methods=['POST'])
def delete_events():
    # Access form properties, get subject information, get events, and delete
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        future_response = executor.submit(eg.delete_messages,
                                          config=flask.current_app.config['AUTOMATIONCONFIG'],
                                          subject=subject)
        future_response.add_done_callback(done)
    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Message deletion started for {subject.id}'
    logger.info(status)

    return status


@bp.route('/task', methods=['POST'])
def task():
    subject = get_subject()
    if not subject:
        return 'none'

    try:
        m = eg.generate_task_files(config=flask.current_app.config['AUTOMATIONCONFIG'],
                                   subject=subject,
                                   instance_path=flask.current_app.instance_path)

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
        future_response = executor.submit(eg.get_conversations,
                                          config=flask.current_app.config['AUTOMATIONCONFIG'],
                                          subject=subject,
                                          instance_path=flask.current_app.instance_path)
        future_response.add_done_callback(done)

    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Retrieving conversations for {subject.id}'
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
    if subject:
        logger.info(f'{subject.id} found in RedCap')
        sessions = dict(s0='Session 0',
                        s1='Session 1',
                        s2='Session 2')
        for key in sessions:
            if key in subject.redcap:
                logger.info(f'{sessions[key]} found')

        return subject.id
    else:
        return 'none'


@bp.route('/files', methods=['POST'])
def download_files():
    subject = get_subject()
    if not subject:
        return 'none'
    csv_path = Path(DOWNLOAD_DIR)
    csvfiles = csv_path.glob(f'*{subject.id}*.csv')
    compression = zipfile.ZIP_STORED
    archive_name = f'{subject.id}.zip'
    with zipfile.ZipFile(Path.home() / archive_name, mode='w', compression=compression) as zf:
        for f in csvfiles:
            zf.write(f, arcname=f.name, compress_type=compression)
    return flask.send_from_directory(Path.home(), archive_name, as_attachment=True)
