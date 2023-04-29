# HABApp:
#   depends on:
#    - params/my_config.yml

import logging
from datetime import datetime, timedelta

from HABApp import DictParameter, Rule
from HABApp.core.items import Item
from HABApp.openhab.definitions import OnOffValue
from HABApp.openhab.items import DatetimeItem, StringItem, SwitchItem
from nibe_f750_heat_pump import NibeF750HeatPump
from nord_pool_market_data import NordPoolMarketData

# Some useful constants
ON = OnOffValue.ON
OFF = OnOffValue.OFF

# Get the configurations parameters stored in the my_config.yml file
configuration = DictParameter('my_config', 'configuration', default_value=None).value

# Defining the following items here will detect any errors early in the development process.
clock_time_of_day_item = StringItem.get_item(configuration["custom_item_names"]['clock_time_of_day_item'])
its_not_early_morning_item = SwitchItem.get_item("Its_Not_Early_Morning")
solar_time_of_day_item = StringItem.get_item(configuration["custom_item_names"]['solar_time_of_day_item'])
v_civil_dawn_item = DatetimeItem.get_item('V_CivilDawn')
v_sunrise_item = DatetimeItem.get_item('V_Sunrise')
v_civil_dusk_start_item = DatetimeItem.get_item('V_CivilDuskStart')
v_civil_dusk_end_item =DatetimeItem.get_item('V_CivilDuskEnd')

class RunAtHABAppStart(Rule):
    """
    A rule that runs at HABApp start.
    """

    def __init__(self):
        super().__init__()
        logger_name = configuration["system"]["MY_LOGGER_NAME"]
        self.log = logging.getLogger(f"{logger_name}.{self.rule_name}")
        self.log.setLevel(logging.INFO)
        self.run.soon(self.init_routine)

    def init_routine(self):
        """
        Initialization routine that is executed at HABApp start.
        """
        self.log.info(f"[{self.rule_name}]: HABApp has started.")
        my_nord_pool_item = Item.get_create_item("MyNordPool", None)
        my_f750_item = Item.get_create_item("MyNibeF750", None)
        my_nord_pool_item.set_value(NordPoolMarketData())
        my_f750_item.set_value(NibeF750HeatPump())

RunAtHABAppStart()

class ClockTimeOfDay(Rule):
    """
    A rule that determines the time of day based on the current hour.
    """

    def __init__(self):
        super().__init__()
        logger_name = configuration["system"]["MY_LOGGER_NAME"]
        self.log = logging.getLogger(f"{logger_name}.{self.rule_name}")
        self.log.setLevel(logging.INFO)
        self.run.soon(self.process_changes)
        next_hour = (datetime.now() + timedelta(hours=1)).replace(minute=0, second=7)
        self.run.every(next_hour, timedelta(hours=1), self.process_changes)

    def process_changes(self):
        """
        Process changes and update items based on the current hour.
        """
        hour = datetime.now().hour
        clock_time_of_day = (
            configuration["time_of_day"]["CLOCK_TIME_OF_DAY"][0]
            if 6 <= hour <= 9
            else configuration["time_of_day"]["CLOCK_TIME_OF_DAY"][1]
            if 9 <= hour <= 17
            else configuration["time_of_day"]["CLOCK_TIME_OF_DAY"][2]
            if 18 <= hour <= 22
            else configuration["time_of_day"]["CLOCK_TIME_OF_DAY"][3]
        )
        self.log.info("[%s]: The time of day (according to the clock) is [%s]", self.rule_name, clock_time_of_day)
        clock_time_of_day_item.oh_post_update_if(clock_time_of_day, not_equal=clock_time_of_day)
        target_value = OFF if 3 < hour < 9 else ON
        its_not_early_morning_item.oh_post_update_if(target_value, not_equal=target_value)

ClockTimeOfDay()

class SolarTimeOfDay(Rule):
    """
    A rule that determines the solar time of day based on various events.
    """

    def __init__(self):
        super().__init__()
        logger_name = configuration["system"]["MY_LOGGER_NAME"]
        self.log = logging.getLogger(f"{logger_name}.{self.rule_name}")
        self.log.setLevel(logging.INFO)
        self.run.soon(self.update_time_of_day, type_of_job='InitJob')
        self.run.on_sun_dawn(callback=self.update_time_of_day, type_of_job='DawnJob')
        self.run.on_sunrise(callback=self.update_time_of_day, type_of_job='SunriseJob')
        self.run.on_sun_dusk(callback=self.update_time_of_day, type_of_job='DuskJob')
        self.run.on_sunset(callback=self.update_time_of_day, type_of_job='SunsetJob')

    def update_time_of_day(self, type_of_job):
        """
        Update the solar time of day based on the given type of job.
        """
        solar_time_of_day = None
        if type_of_job == 'DawnJob':
            solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][0]
        elif type_of_job == 'SunriseJob':
            solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][1]
        elif type_of_job == 'SunsetJob':
            solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][2]
        elif type_of_job == 'DuskJob':
            solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][3]
        else:
            # Not triggered by a channel. Probably because the system just started.
            # Let's find out manually where we are then...
            datetime_now = datetime.now()

            dawn_start = v_civil_dawn_item.get_value(datetime_now)
            day_start = v_sunrise_item.get_value(datetime_now)
            dusk_start = v_civil_dusk_start_item.get_value(datetime_now)
            night_start = v_civil_dusk_end_item.get_value(datetime_now)

            if dawn_start <= datetime_now < day_start:
                solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][0]
            elif day_start <= datetime_now < dusk_start:
                solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][1]
            elif dusk_start <= datetime_now < night_start:
                solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][2]
            else:
                solar_time_of_day = configuration["time_of_day"]["SOLAR_TIME_OF_DAY"][3]

        self.log.info("[%s]: The solar time of day is [%s]", self.rule_name, solar_time_of_day)
        solar_time_of_day_item.oh_send_command(solar_time_of_day)

SolarTimeOfDay()
