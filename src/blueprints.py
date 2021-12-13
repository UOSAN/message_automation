from pathlib import Path
import logging.config
import zipfile
from datetime import date

import flask

import src.event_generator as eg
from src.redcap import Redcap, RedcapError
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


# get participant object from id in form
def get_participant():
    participant_id = flask.request.form['participant']
    if len(participant_id) != 6 or not participant_id.startswith('ASH'):
        logger.warning(f'Warning: {participant_id} is not in the form \"ASHnnn\"')

    rc = Redcap(api_token=flask.current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])
    try:
        participant = rc.get_participant(participant_id)
    except RedcapError as err:
        logger.error(str(err))
        return None
    return participant


@bp.route('/diary1', methods=['POST'])
def diary1():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        m = eg.daily_diary_one(config=flask.current_app.config['AUTOMATIONCONFIG'], participant=participant)

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.info(m)
    return 'success'


@bp.route('/diary3', methods=['POST'])
def diary2():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        m = eg.daily_diary_three(config=flask.current_app.config['AUTOMATIONCONFIG'], participant=participant)

    except Exception as err:
        logger.error(str(err))
        return str(err)

    logger.info(m)
    return 'success'


@bp.route('/messages', methods=['POST'])
def generate_messages():
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        future_response = executor.submit(eg.generate_messages,
                                          config=flask.current_app.config['AUTOMATIONCONFIG'],
                                          participant=participant,
                                          instance_path=flask.current_app.instance_path)
        future_response.add_done_callback(done)
    except Exception as err:
        logger.error(str(err))
        return str(err)

    status = f'Message generation started for {participant.participant_id}'
    logger.info(status)
    return status


@bp.route('/delete', methods=['POST'])
def delete_events():
    # Access form properties, get participant information, get events, and delete
    participant = get_participant()
    if not participant:
        return 'none'

    try:
        future_response = executor.submit(eg.delete_messages,
                                          config=flask.current_app.config['AUTOMATIONCONFIG'],
                                          participant=participant)
        future_response.add_done_callback(done)
    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Message deletion started for {participant.participant_id}'
    logger.info(status)

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

    logger.info(m)
    return m


@bp.route('/responses', methods=['POST'])
def responses():
    participant = get_participant()
    if not participant:
        return 'none'
    try:
        future_response = executor.submit(eg.get_conversations,
                                          config=flask.current_app.config['AUTOMATIONCONFIG'],
                                          participant=participant,
                                          instance_path=flask.current_app.instance_path)
        future_response.add_done_callback(done)

    except ValueError as err:
        logger.error(str(err))
        return str(err)

    status = f'Retrieving conversations for {participant.participant_id}'
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

    #    daily_messages = list(reversed(lines))
    return flask.render_template('progress.html', messages=daily_messages)


@bp.route('/')
def index():
    return flask.render_template('index.html')


@bp.route('/validate', methods=['POST'])
def validate():
    participant = get_participant()
    if participant:
        logger.info(f'{participant.participant_id} found in RedCap')
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
