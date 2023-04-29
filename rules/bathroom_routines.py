# HABApp:
#   depends on:
#    - rules/001_init.py
#    - params/my_config.yml
#   reloads on:
#    - params/my_config.yml

import logging
from datetime import datetime, timedelta

from HABApp import DictParameter, Rule
from HABApp.core.events import ValueChangeEventFilter
from HABApp.openhab.definitions import OnOffValue, OpenClosedValue, UpDownValue
from HABApp.openhab.items import (NumberItem, SwitchItem, GroupItem, DatetimeItem)
from mypushover import send_pushover_message, PUSHOVER_PRIO
from myutils import PRIO, play_sound

# Some useful constants
ON = OnOffValue.ON
OFF = OnOffValue.OFF
OPEN = OpenClosedValue.OPEN
CLOSED = OpenClosedValue.CLOSED
UP = UpDownValue.UP
DOWN = UpDownValue.DOWN


SENSOR_GROUP = 'G_Bathroom_Hum_Control' # All sensors belonging to this group will be used for measuring
NEVER_TRY_PUSH_BELOW = 50
HUMIDITY_ACCEPTABLE = 41
HUM_HYSTERESIS = 5
BLOCK_FAN_MINS_AFTER_TIMEOUT = 30 # Minutes to block restarting of the fan in case FAN_MAX_TIME was reached
DEBUGGING = False

# Get the configurations parameters stored in the my_config.yml file
configuration = DictParameter('my_config', 'configuration', default_value=None).value

flatulence_extra_vent_item = SwitchItem.get_item('Flatulence_Extra_Vent')
flatulence_button_item = SwitchItem.get_item('Flatulence_Button')
excess_hum_extra_vent_item = SwitchItem.get_item("Excess_Hum_Extra_Vent")
bathroom_block_fan_until_item = DatetimeItem.get_item("Bathroom_Block_Fan_Until")

class FlatulenceRule(Rule):
    def __init__(self):
        super().__init__()
        self.log = logging.getLogger(f'{configuration["system"]["MY_LOGGER_NAME"]}.{self.rule_name}')
        self.log.setLevel(logging.INFO)
        flatulence_button_item.listen_event(self.process_changes, ValueChangeEventFilter(value=ON))

    def process_changes(self, event=None):
        """
        Process changes when the flatulence button is pushed.
        """
        self.log.info('Flatulence button was pushed')
        flatulence_extra_vent_item.on()  # This will reset the timer
        play_sound('joke_sting.mp3', PRIO['MODERATE'], tts_room='Badrummet', tts_volume=50)

FlatulenceRule()

import logging
from datetime import datetime, timedelta

class HumControl(Rule):
    def __init__(self):
        """
        The bathroom ventilation rule
        """
        super().__init__()
        self.log = logging.getLogger(f"{configuration['system']['MY_LOGGER_NAME']}.{self.rule_name}")
        self.log.setLevel(logging.INFO)
        self.run.every(timedelta(seconds=10), 300, self.process_changes)  # Wait for 10 seconds and then run with 5-minute intervals
        excess_hum_extra_vent_item.listen_event(self.timer_timed_out, ValueChangeEventFilter(value=OFF))

    def process_changes(self, event=None):
        hum_items = []
        hum_values = []

        if bathroom_block_fan_until_item.get_value(None) is None:
            block_until = datetime.today() + timedelta(minutes=BLOCK_FAN_MINS_AFTER_TIMEOUT)
            bathroom_block_fan_until_item.oh_post_update(block_until)
            return

        for hum_item in GroupItem.get_item("G_Bathroom_Hum_Control").members:
            hum_items.append(hum_item)
            hum_values.append(hum_item.value if hum_item.value is not None else 0)

        current_humidity = max(hum_values)

        if current_humidity < HUMIDITY_ACCEPTABLE:
            self.log.debug("Current measured humidity is only: %d%% RH, no need to force ventilation.", current_humidity)
            return self.target_hum_reached()

        average_hums = []
        highest_value = 0

        for hum_item in hum_items:
            now = datetime.now()
            avg_hum = hum_item.get_persistence_data(start_time=datetime.today() - timedelta(hours=48), end_time=now).average()

            if avg_hum is None:
                self.log.error("Failed to get persistence data for sensor: [%s]", hum_item.name)
            else:
                value = round(avg_hum)
                self.log.debug("Got a humidity average for sensor: [%s]: %d%% RH", hum_item.name, value)

                if value > highest_value:
                    highest_value = value
                    average_hums.append(value)

        if average_hums:
            avg_hum = round(sum(average_hums) / float(len(average_hums)))
        else:
            avg_hum = 0

        target_hum = max([avg_hum + HUM_HYSTERESIS, NEVER_TRY_PUSH_BELOW])
        stats = f"Current hum: {current_humidity}, Avg hum: {avg_hum}, Target hum: {target_hum}"
        self.log.debug(stats)

        if current_humidity <= target_hum:
            self.log.debug("Current humidity is below or equal to target humidity")
            return self.target_hum_reached()

        if excess_hum_extra_vent_item.is_off():
            earliest_start = bathroom_block_fan_until_item.value

            if earliest_start < datetime.now():
                message = f"{earliest_start} is in the past, so we start the fan now. {stats}"
                self.log.debug(message)

                if DEBUGGING:
                    send_pushover_message(message, title="BATHROOM VENTILATION")

                excess_hum_extra_vent_item.on()
            else:
                self.log.debug(f"{earliest_start} is in the future, so we'll have to wait")
        else:
            self.log.debug("We are currently in the process of ventilating the bathroom")

    def timer_timed_out(self, event=None):
        block_until = datetime.today() + timedelta(minutes=BLOCK_FAN_MINS_AFTER_TIMEOUT)
        bathroom_block_fan_until_item.oh_post_update(block_until)
        message = f"Timer timed out. We may start the fan again after: {block_until}."
        self.log.debug(message)
        if DEBUGGING:
            send_pushover_message(message, title="BATHROOM VENTILATION")

    def target_hum_reached(self):
        """
        Check if the measured humidity is below or equal to the target humidity.
        """
        # Is the fan currently running under the control of this script?
        if excess_hum_extra_vent_item.is_on():
            # The humidity target has been reached within the time limit.
            # Cancel the Timer by using postUpdate so it won't trigger again.
            if DEBUGGING:
                send_pushover_message("Great success! The humidity target has been reached within the time limit.",
                                    title="BATHROOM VENTILATION")
            excess_hum_extra_vent_item.off()

HumControl()

class SummerVentilation(Rule):
    def __init__(self):
        super().__init__()
        self.log = logging.getLogger(f"{configuration['system']['MY_LOGGER_NAME']}.{self.rule_name}")
        self.log.setLevel(logging.INFO)

        self.run.soon(self.process_changes)
        self.run.every_hour(self.process_changes)

        self.summer_extra_vent_item = SwitchItem.get_item("Summer_Extra_Vent")
        self.particle_concentration_pm2_5_item = NumberItem.get_item("Particle_Concentration_PM2_5")
        self.indoor_temp_item = NumberItem.get_item("Temp_Hallway")
        self.outdoor_temp_item = NumberItem.get_item("Nibe_40004")

    def process_changes(self, event=None):
        # Check if it's summer
        if datetime.now().month not in [5, 6, 7, 8]:
            return

        self.log.debug("It's summer. Checking if it's too hot indoors and cooler outside to enable extra ventilation.")

        pm2_5_concentration = int(self.particle_concentration_pm2_5_item.get_value(0))
        indoor_temp = round(self.indoor_temp_item.value)
        outdoor_temp = round(self.outdoor_temp_item.value)

        message = f"Extra summer ventilation. PM2.5: {pm2_5_concentration}, Outdoor: {outdoor_temp}, Indoor: {indoor_temp}"

        if pm2_5_concentration <= 10 and indoor_temp >= 25 and outdoor_temp < indoor_temp - 2:
            if self.summer_extra_vent_item.is_off:
                self.summer_extra_vent_item.on()
                self.log.debug(message)
                send_pushover_message(message, title="SUMMER VENTILATION", priority=PUSHOVER_PRIO["LOW"])
        else:
            self.summer_extra_vent_item.off()

SummerVentilation()
