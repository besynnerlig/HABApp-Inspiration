import logging
from clickatell.http import Http
from HABApp import DictParameter

configuration = DictParameter('my_config', 'configuration', default_value=None).value
clickatell_configuration = configuration["clickatell"]

log = logging.getLogger(f'{configuration["system"]["MY_LOGGER_NAME"]}.mysms')

def send_sms(message, subscriber='Default'):
    """
    Sends an SMS message through the ClickaTell gateway.
    Example: send_sms("Hello")
    Example: send_sms("Hello", 'Amanda')
    
    :param message: SMS text
    :param subscriber: Subscriber. A numeric phone number or a phonebook name entry (string)
    """

    phone_number = clickatell_configuration['phonebook'].get(subscriber, None)
    if phone_number is None:
        if subscriber.isdigit():
            phone_number = subscriber
        else:
            log.error(f'Subscriber [{subscriber}] was not found in the phone book')
            return

    clickatell = Http(clickatell_configuration['user'], clickatell_configuration['password'], clickatell_configuration['apiid'])
    log.info(f"Sending SMS to: [{phone_number}]")

    unicode_message = ''.join(r'{:04X}'.format(ord(chr)) for chr in message)

    response = clickatell.sendMessage([phone_number], unicode_message, extra={'from': clickatell_configuration['sender'], 'unicode': 1})
    for entry in response:
        log.info(entry['error'])
