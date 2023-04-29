import json
import logging
import subprocess
from datetime import date, datetime
from typing import Dict, Optional, Union

from HABApp import DictParameter
from HABApp.mqtt.items import MqttItem
from HABApp.openhab.definitions import OnOffValue, OpenClosedValue, UpDownValue
from HABApp.openhab.items import NumberItem, StringItem

configuration = DictParameter('my_config', 'configuration', default_value=None).value
lighting_configuration = DictParameter('lighting_config', 'configuration', default_value=None).value
LIGHT_LEVEL = lighting_configuration["lighting"]["LIGHT_LEVEL"]
SOLAR_TIME_OF_DAY = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"]
CLOCK_TIME_OF_DAY = configuration["time_of_day"]["CLOCK_TIME_OF_DAY"]
lametric_configuration = configuration["lametric"]
customItemNames = configuration["custom_item_names"]
sonos = configuration["sonos"]

log = logging.getLogger(f'{configuration["system"]["MY_LOGGER_NAME"]}.myutils')
log.setLevel(logging.INFO)

# Some useful constants
ON = OnOffValue.ON
OFF = OnOffValue.OFF
OPEN = OpenClosedValue.OPEN
CLOSED = OpenClosedValue.CLOSED
UP = UpDownValue.UP
DOWN = UpDownValue.DOWN

SPC_AREA_MODE = {'unset': 0, 'partset_a': 1, 'partset_b': 2, 'set': 3}
PRIO = {'LOW': 0, 'MODERATE': 1, 'HIGH': 2, 'EMERGENCY': 3}

def calendar_days_between(start_date_or_datetime: Union[date, datetime], end_date_or_datetime: Union[date, datetime]) -> int:
    '''
    Get the number of calendar days between two dates or datetimes.
    '''
    start_date = start_date_or_datetime.date() if isinstance(start_date_or_datetime, datetime) else start_date_or_datetime
    end_date = end_date_or_datetime.date() if isinstance(end_date_or_datetime, datetime) else end_date_or_datetime
    num_days_between = (start_date - end_date).days
    return num_days_between

def get_key_for_value(dictionary: Dict[str, str], value: str) -> Optional[str]:
    """
    In a given dictionary, get the first key that has a value matching the one provided.

    Args:
        dictionary (dict): the dictionary to search
        value (str): the value to match to a key

    Returns:
        str or None: string representing the first key with a matching value, or
            None if the value is not found
    """
    return next((k for k, v in dictionary.items() if v == value), None)

def spc_area_is_set():
    '''
    Returns True if the SPC alarm area 1 is either partial or fully set otherwise returns False
    '''
    item_value = StringItem.get_item('SPC_Area_1_Mode').value
    if item_value is not None:
        return SPC_AREA_MODE.get(item_value, 0) > 0
    else:
        return False

def spc_area_is_fully_set():
    '''
    Returns True if the SPC alarm area 1 is fully set otherwise returns False
    '''
    item_value = StringItem.get_item('SPC_Area_1_Mode').value
    if item_value is not None:
        return SPC_AREA_MODE.get(item_value, 0) == 3
    else:
        return False

def spc_area_is_partially_set():
    '''
    Returns True if the SPC alarm area 1 is fully set otherwise returns False
    '''
    item_value = StringItem.get_item('SPC_Area_1_Mode').value
    if item_value is not None:
        return SPC_AREA_MODE.get(item_value, 0) == 1
    else:
        return False

def get_compass_direction(degrees):
    '''
    Returns the compass direction abbreviation (Swedish) for the given compass degree
    '''
    COMPASS_DIRECTIONS = {
        (0, 22.5): 'N',
        (22.5, 67.5): 'NNO',
        (67.5, 112.5): 'O',
        (112.5, 157.5): 'OSO',
        (157.5, 202.5): 'S',
        (202.5, 247.5): 'SSO',
        (247.5, 292.5): 'V',
        (292.5, 337.5): 'VNV',
        (337.5, 360): 'N'
    }
    for degree_range, direction in COMPASS_DIRECTIONS.items():
        if degree_range[0] <= degrees < degree_range[1]:
            return direction

def is_light_level_bright() -> bool:
    """Checks if the light level is bright."""
    light_level_item = NumberItem.get_item(customItemNames['sysLightLevel'])
    return light_level_item.value == LIGHT_LEVEL['BRIGHT'] if light_level_item.value is not None else False

def is_light_level_shady() -> bool:
    """Checks if the light level is shady."""
    light_level_item = NumberItem.get_item(customItemNames['sysLightLevel'])
    return light_level_item.value <= LIGHT_LEVEL['SHADY'] if light_level_item.value is not None else False

def is_light_level_dark() -> bool:
    """Checks if the light level is dark."""
    light_level_item = NumberItem.get_item(customItemNames['sysLightLevel'])
    return light_level_item.value <= LIGHT_LEVEL['DARK'] if light_level_item.value is not None else False

def is_light_level_black() -> bool:
    """Checks if the light level is black."""
    light_level_item = NumberItem.get_item(customItemNames['sysLightLevel'])
    return light_level_item.value <= LIGHT_LEVEL['BLACK'] if light_level_item.value is not None else False

def is_clock_night() -> bool:
    """Checks if the clock indicates night."""
    clock_time_item = StringItem.get_item(customItemNames['clock_time_of_day_item'])
    return clock_time_item.value == CLOCK_TIME_OF_DAY[3] if clock_time_item.value is not None else False

def is_solar_night() -> bool:
    """Checks if the solar position indicates night."""
    solar_time_item = StringItem.get_item(customItemNames['solar_time_of_day_item'])
    return solar_time_item.value == SOLAR_TIME_OF_DAY[3] if solar_time_item.value is not None else False

def calculate_speech_time_secs(text: str) -> int:
    '''Calculates the delay required for speaking a text string based on the character length and speaking speed.'''
    CHARACTERS_PER_SECOND = 6
    ADDITIONAL_DELAY_SECONDS = 3
    CHARACTER_LENGTH_ADJUSTMENT_FACTOR = 1.2
    character_count = len(text)
    return int((character_count / CHARACTERS_PER_SECOND) * CHARACTER_LENGTH_ADJUSTMENT_FACTOR + ADDITIONAL_DELAY_SECONDS)

NOTIFICATION_DEFAULT_LANGUAGE = "sv-SE"
NOTIFICATION_DEFAULT_ENGINE = "neural"
NOTIFICATION_DEFAULT_ROOM = "Vardagsrummet"
NOTIFICATION_DEFAULT_GENDER = "female"
NOTIFICATION_DEFAULT_VOICE = "Elin"
NOTIFICATION_DEFAULT_ONLY_WHEN_PLAYING = False
NOTIFICATION_DEFAULT_TIMEOUT = 0
NOTIFICATION_DEFAULT_MP3_TIMEOUT = 15

class Notification:
    def __init__(self, notification_or_url, priority=PRIO['MODERATE'], **kwargs):
        self.notification_or_url = notification_or_url
        self.priority = priority
        self.room = kwargs.get('tts_room', NOTIFICATION_DEFAULT_ROOM)
        self.volume = kwargs.get('tts_volume', None)
        self.language = kwargs.get('tts_lang', sonos.get("rooms", {}).get(self.room, {}).get("tts_lang", NOTIFICATION_DEFAULT_LANGUAGE)) # Use param if exist, else config, else default
        self.voice = kwargs.get('tts_voice', sonos.get("rooms", {}).get(self.room, {}).get("tts_voice", NOTIFICATION_DEFAULT_VOICE))
        self.gender = kwargs.get('tts_gender', sonos.get("rooms", {}).get(self.room, {}).get("tts_gender", NOTIFICATION_DEFAULT_GENDER))
        self.engine = kwargs.get('tts_engine', sonos.get("rooms", {}).get(self.room, {}).get("tts_engine", NOTIFICATION_DEFAULT_ENGINE))
        self.only_when_playing = kwargs.get('only_when_palying', NOTIFICATION_DEFAULT_ONLY_WHEN_PLAYING)
        self.delay_ms = kwargs.get('delay_ms', 0) if 1 <= kwargs.get('delay_ms', 0) <= 1000 else 500
        self.timeout = kwargs.get('timeout', NOTIFICATION_DEFAULT_TIMEOUT)
        self.mp3_timeout = NOTIFICATION_DEFAULT_MP3_TIMEOUT
        self.language_server = f'http://{sonos["TTS_HOST"]}:5601/api/generate'
        self.mqtt_topic = ""
        self.payload = ""

    @property
    def volume(self):
        if not self._volume or self._volume >= 70:
            if self.priority == PRIO['LOW']:
                return 30
            elif self.priority == PRIO['MODERATE']:
                return 40
            elif self.priority == PRIO['HIGH']:
                return 60
            elif self.priority == PRIO['EMERGENCY']:
                return 70
            else:
                return 50
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value

    def should_play(self):
        # Get current hour
        current_hour = datetime.now().hour

        # Check if current hour is outside the range of 7 AM to 9 PM
        is_outside_range = current_hour < 7 or current_hour > 21

        # Check if outside range or if the SPC alarm is set and priority level is low
        if (is_outside_range or spc_area_is_set()) and self.priority <= PRIO['MODERATE']:
            log_message = f"Message priority [{get_key_for_value(PRIO, self.priority)}] is too low to play the notification '{self.notification_or_url}' at this moment."
            log.info(log_message)
            return False
        return True

    def play_mp3(self):
        # Get current hour
        return self.notification_or_url.lower().endswith('.mp3')

    @property
    def mqtt_topic(self):
        # Get the the mqtt topic
        return self._mqtt_topic

    @mqtt_topic.setter
    def mqtt_topic(self, value):
        if self.play_mp3():
            self._mqtt_topic = 'sonos/set/notify' if self.room == "All" else f'sonos/set/{self.room}/notify'
        else:
            self._mqtt_topic = "sonos/set/speak" if self.room == "All" else f'sonos/set/{self.room}/speak'

    @property
    def payload(self):
        # Get the payload
        return self._payload

    @payload.setter
    def payload(self, value):
        if self.play_mp3():
            track_uri = f'http://{sonos["TTS_HOST"]}:5601/cache/sounds/{self.notification_or_url}'
            self._payload = { "trackUri": track_uri, "volume": self.volume, "timeout": self.mp3_timeout, "onlyWhenPlaying": self.only_when_playing }
            if self.delay_ms and 0 < self.delay_ms < 2001:
                self._payload['delayMs'] = self.delay_ms
            if self.timeout and 0 < self.timeout < 250:
                self._payload['timeout'] = self.timeout
        else:
            self._payload = { "text": self.notification_or_url, "endpoint": self.language_server, "lang": self.language, "gender": self.gender, "engine": self.engine, "volume": self.volume, "onlyWhenPlaying": self.only_when_playing }
            if self.voice is not None:
                self._payload['name'] = self.voice
            if self.delay_ms and 0 < self.delay_ms < 2001:
                self._payload['delayMs'] = self.delay_ms
            if self.timeout and 0 < self.timeout < 250:
                self._payload['timeout'] = self.timeout

    def play(self):
        # Play the notification
        if not self.should_play():
            return False
        mqtt_pub(self.mqtt_topic, json.dumps(self.payload))
        return True

def play_notification(notification_or_url, priority=PRIO['MODERATE'], **kwargs):
    '''
    Plays a notification on the Sonos system.
    The notification can be either a text string or an URL to an mp3 file.
    '''
    notification = Notification(notification_or_url, priority, **kwargs)
    return notification.play()

def speak_text(text_to_speak, priority=PRIO['MODERATE'], **keywords):
    '''
    Text To Speak function. First argument is positional and mandatory.
    Remaining arguments are optionally keyword arguments.
    Example: speak_text("Hello")
    Example: speak_text("Hello", PRIO['HIGH'], tts_room='Kitchen', tts_volume=42, tts_lang='en-GB', tts_voice='Brian')
    @param param1: Text to speak (positional argument)
    @param param2: priority as defined by PRIO. Defaults to PRIO['MODERATE']
    @param tts_room: Room to speak in. Defaults to "TV-Rummet".
    @return: this is a description of what is returned
    '''
    return play_notification(text_to_speak, priority, **keywords)

def play_sound(play_file, ttsPrio=PRIO['MODERATE'], **keywords):
    '''
    To play a short sound file as a notification
    '''
    return play_notification(play_file, ttsPrio, **keywords)

def mqtt_pub(topic, payload):
    '''
    Publishes a MQTT message on the default brooker
    '''
    log.debug('%s <- %s', topic, payload)
    MqttItem.get_create_item(topic).publish(payload)

def send_notification_to_lametric(notification_text: str = 'HELLO!', notification_prio: int = PRIO['MODERATE'], **keywords: Dict) -> bool:
    '''
    Sends a notification to the LaMetric device.
    Documentation @ https://lametric-documentation.readthedocs.io/en/latest/reference-docs/device-notifications.html
    Possible keywords: sound, icon, autoDismiss, lifeTime, iconType
    '''
    log.debug('Sending a notification to LaMetric')

    def is_quiet_hours(start_hour, end_hour):
        """Returns True if the current time is within the quiet hours."""
        now_hour = datetime.now().hour
        return ((now_hour < start_hour) or (now_hour > end_hour))

    def should_play_sound(notification_prio):
        """Returns True if a sound should be played with the notification."""
        if notification_prio <= PRIO['MODERATE'] and spc_area_is_set():
            return False
        if is_quiet_hours(7, 21):
            return False
        return True    

    sound = lametric_configuration.get('DEFAULT_NOTIFICATION_SOUND') if 'sound' not in keywords else keywords['sound']
    icon = lametric_configuration.get('DEFAULT_ICON') if 'icon' not in keywords else keywords['icon']
    auto_dismiss = True if 'autoDismiss' not in keywords else keywords['autoDismiss']
    life_time = lametric_configuration.get('DEFAULT_LIFETIME') if 'lifeTime' not in keywords else keywords['lifeTime']
    icon_type = 'info' if 'iconType' not in keywords else keywords['iconType'] # [none|info|alert]

    url = f'https://{lametric_configuration["HOST"]}:{lametric_configuration["PORT"]}/api/v2/device/notifications'
    priority = 'critical' #"priority": "[info|warning|critical]" Must be critical to break through the app
    #"icon_type":"[none|info|alert]",
    #"lifeTime":<milliseconds>,
    # cycles – the number of times message should be displayed. If cycles is set to 0, notification will stay on the screen until user dismisses it manually or you can dismiss it via the API (DELETE /api/v2/device/notifications/:id). By default it is set to 1.

    cycles = 1 if auto_dismiss else 0 # cycles – the number of times message should be displayed. If cycles is set to 0, notification will stay on the screen until user dismisses it manually or you can dismiss it via the API (DELETE /api/v2/device/notifications/:id). By default it is set to 1.
    payload = { 'priority': priority, 'icon_type': icon_type, 'lifeTime': life_time, 'model': { 'frames': [ { 'icon': icon, 'text': notification_text} ], 'cycles': cycles } }
    if should_play_sound(notification_prio):
        payload['model']['sound'] = { 'category': 'notifications', 'id': sound, 'repeat': 1 }
    else:
        log.info(f"The notification_prio argument {notification_prio} is too low to play a sound together with the notification at this moment")

    args_list = [
        'curl',
        '-X',
        'POST',
        '-u',
        f'dev:{lametric_configuration["API_KEY"]}',
        '-H',
        'Content-Type: application/json',
        '-d',
        json.dumps(payload),
        url,
        '--insecure'
    ]

    result = subprocess.run(args_list, capture_output=True)
    if result.returncode != 0:
        log.error(f"Error executing command: {result.returncode}")
        return False
    return True

def greeting():
    return f'God{StringItem.get_item(customItemNames["clock_time_of_day_item"]).value.lower()}'

r'''
                                 Safety pig has arrived!

                                  _._ _..._ .-',     _.._(`))
                                 '-. `     '  /-._.-'    ',/
                                    )         \            '.
                                   / _    _    |             \
                                  |  a    a    /              |
                                  \   .-.                     ;
                                   '-('' ).-'       ,'       ;
                                      '-;           |      .'
                                         \           \    /
                                         | 7  .__  _.-\   \
                                         | |  |  ``/  /`  /
                                        /,_|  |   /,_/   /
                                           /,_/      '`-'
'''
