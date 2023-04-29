import threading
from pushover import Client, Message
from HABApp import DictParameter

configuration = DictParameter('my_config', 'configuration', default_value=None).value
pushover_configuration = configuration["pushover"]
PUSHOVER_PRIO = configuration["pushover"]["PUSHOVER_PRIO"]
PUSHOVER_DEF_DEV = configuration["pushover"]["PUSHOVER_DEF_DEV"]

client = Client(pushover_configuration["user_token"], pushover_configuration["api_token"])

def send_pushover_message(
    message,
    title="Hejsan",
    device=PUSHOVER_DEF_DEV,
    priority=PUSHOVER_PRIO['NORMAL'],
    url=None,
    url_title=None,
    **keywords
):
    """
    Sends a Pushover notification using threading to prevent the script from taking too long.
    """
    msg = Message(message, title=title, device=device, priority=priority, url=url, url_title=url_title)
    threading.Timer(0, client.send, [msg]).start()
    return True  # if r.status_code == 200 else False
