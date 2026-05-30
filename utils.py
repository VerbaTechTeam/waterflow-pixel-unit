from phew import logging
import json

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        logging.debug(f'Cannot read: {filename}')
        return { }

def save_json(filename, content):
    try:
        with open(filename, 'w') as f:
            json.dump(content, f)
            return True
    except:
        logging.debug(f'Cannot write {content} into {filename}')
        return False

DEFAULT_GPIO = {
    'dout': 19,
    'sensor': 18,
    'off': 20
}

def normalize_gpio_config(data):
    gpio = DEFAULT_GPIO.copy()
    if data is None:
        data = {}
    for key in gpio:
        if key in data:
            value = data[key]
            if isinstance(value, int) and 0 <= value <= 28:
                gpio[key] = value
    return gpio

def load_gpio_config():
    return normalize_gpio_config(load_json('gpio.json'))

def save_gpio_config(data):
    return save_json('gpio.json', normalize_gpio_config(data))
