from phew import server, connect_to_wifi, access_point, logging, ntp
from network import hostname
import uasyncio
import machine
import json
import config
from waterflowdriver import WaterflowDriver
import ubinascii
import auth
from utils import load_json, save_json, load_gpio_config


net = load_json('net.json')
driver = WaterflowDriver()
name = config.device['application-name']
hostname(name)
ip = connect_to_wifi(net['ssid'], net['pass'])
if ip is None:
    ip = access_point(net['ap-ssid'], net['ap-pass'])
    print('AP IP', ip)
    logging.info(f'> {name} – uruchomiono AP: IP ({ip})')
else:
    print('IP', ip)
    logging.info(f'> {name} – połączenie z siecią: IP ({ip})')
    ntp.fetch()
auth.ensure_default_setup()

def load_logs():
    filename = logging.log_file
    try:
        with open(filename, 'r') as f:
            return f.read()
    except:
        logging.debug(f'Cannot read: {filename}')
        return { }
    

@server.route("/api/info", methods=["GET"])
def get_device_info(request):
    return json.dumps(config.device), 200, {"Content-type": "application/json"}

@server.route("/api/logs", methods=["GET"])
def get_logs(request):
    content = load_logs()
    lines = content.split("\n")
    return json.dumps(lines), 200, {"Content-type": "application/json"}

@server.route("/api/logs", methods=["DELETE"])
def clear_logs(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    
    import os
    filename = logging.log_file
    content = load_logs()
    try:
        os.remove(filename)
        logging.info('> log clear')
    except:
        logging.debug(f'Cannot clear log file')
        return json.dumps({"message": "Internal Server Error"}), 500, {"Content-type": "application/json"}
    newCredentials = auth.refresh_token(user)
    return json.dumps({"logs": content.split("\n"), "newCredentials": newCredentials}), 200, {"Content-type": "application/json"}

@server.route("/api/restart", methods=["POST"])
def restart(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin", "editor"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}

    logging.info('> restarting by http request')
    restartCountdown = 10
    if "defaultRestartCountdown" in driver.data:
        restartCountdown = driver.data["defaultRestartCountdown"]
    newCredentials = auth.refresh_token(user)
    driver.restartCountdown = restartCountdown
    return json.dumps({"restartCountdown": restartCountdown, "newCredentials": newCredentials}), 200, {"Content-type": "application/json"}

@server.route("/api/secure/admin/reset", methods=["POST"])
def reset_admin_pass(request):
    if 'secure' not in request.headers or request.headers['secure'] != config.secured['secure']:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    
    users = load_json('users.json')
    if 'pass' not in request.data:
        return json.dumps({"message": "Bad Request"}), 400, {"Content-type": "application/json"}

    if len(request.data['pass']) < 7:
        return json.dumps({"message": "Not Acceptable"}), 406, {"Content-type": "application/json"}

    users['admin']['pass'] = request.data['pass']
    if save_json('users.json', users):
        return json.dumps({"message": "Accepted"}), 202, {"Content-type": "application/json"}
    else:
        return json.dumps({"message": "Internal Server Error"}), 500, {"Content-type": "application/json"}

@server.route("/api/secure/auth", methods=["POST"])
def user_auth(request):
    auth.apply_auth_headers(request)
    if 'user' not in request.headers or 'pass' not in request.headers:
        return json.dumps({'message': 'Unauthorized'}), 401, {"Content-type": "application/json"}
    username = request.headers['user']
    password = request.headers['pass']
    users = load_json('users.json')
    if username not in users or password != users[username]['pass']:
        return json.dumps({'message': 'Unauthorized'}), 401, {"Content-type": "application/json"}
    
    return json.dumps(auth.refresh_token(username)), 200, {"Content-type": "application/json"}
    

@server.route("/api/secure/pass", methods=["PATCH"])
def user_pass_change(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    
    new_pass = request.data.get('pass', "")
    if len(request.data['pass']) < 7:
        return json.dumps({'message': 'Password too short'}), 406, {"Content-type": "application/json"}
    
    users = load_json('users.json')
    users[user]['pass'] = new_pass
    
    if save_json('users.json', users):
        new_credentials = auth.refresh_token(user)
        return json.dumps({'username': user, 'newCredentials': new_credentials}), 202, {"Content-type": "application/json"}
    else:
        logging.info(f'> cannot change password for {user} – saving problems')
        return json.dumps({'message': 'Internal Server Error'}), 500, {"Content-type": "application/json"}
    
@server.route("/api/data", methods=["PUT", "PATCH"])
def change_data(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin", "editor"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    
    old = load_json('data.json')
    data = request.data
    if 'nol' not in data:
        data['nol'] = 3
    new = data
    if request.method == "PATCH":
        new = old.copy()
        new.update(data)
    
    if save_json('data.json', new):
        new_credentials = auth.refresh_token(user)
        return json.dumps({'before': old, 'after': new, 'newCredentials': new_credentials}), 202, {"Content-type": "application/json"}
    else:
        return json.dumps({'message': 'Internal Server Error'}), 500, {"Content-type": "application/json"}
    

@server.route("/api/secure/admin", methods=["GET"])
def get_secure(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    newCredentials = auth.refresh_token(user)
    return json.dumps({'secure': config.secured, 'newCredentials': newCredentials}), 200, {"Content-type": "application/json"}


@server.route("/api/secure/gpio", methods=["GET"])
def get_gpio(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    newCredentials = auth.refresh_token(user)
    return json.dumps({'gpio': load_gpio_config(), 'newCredentials': newCredentials}), 200, {"Content-type": "application/json"}

@server.route("/api/secure/gpio", methods=["PUT", "PATCH"])
def change_gpio(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}

    allowed_keys = ['pixel', 'sensor', 'off']
    data = request.data
    for key in data:
        if key not in allowed_keys:
            return json.dumps({"message": "Bad Request"}), 400, {"Content-type": "application/json"}
        value = data[key]
        if not isinstance(value, int) or value < 0 or value > 28:
            return json.dumps({"message": "Bad Request"}), 400, {"Content-type": "application/json"}

    old = load_gpio_config()
    new = data
    if request.method == "PATCH":
        new = old.copy()
        new.update(data)

    if driver.configure_gpio(new):
        newCredentials = auth.refresh_token(user)
        return json.dumps({'before': old, 'after': load_gpio_config(), 'newCredentials': newCredentials}), 202, {"Content-type": "application/json"}
    else:
        return json.dumps({'message': 'Internal Server Error'}), 500, {"Content-type": "application/json"}

@server.route("/api/secure/users", methods=["GET"])
def list_users_groups(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    newCredentials = auth.refresh_token(user)
    data = auth.get_users_with_groups()
    return json.dumps({'users': data, 'newCredentials': newCredentials}), 200, {"Content-type": "application/json"}

@server.route("/api/secure/users", methods=["POST"])
def create_user_with_groups(request):
    admin_user = auth.authenticate(request)
    if not admin_user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(admin_user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    
    data = request.data
    username = data.get('user')
    password = data.get('pass')
    groups = data.get('groups', ['editor'])
    
    if not username or not password:
        return json.dumps({"message": "Missing data"}), 400, {"Content-type": "application/json"}
    if not auth.create_user_with_groups(username, password, groups):
        return json.dumps({'message': 'Conflict or password too short'}), 409, {"Content-type": "application/json"}
    newCredentials = auth.refresh_token(user)
    return json.dumps({'username': username, 'groups': groups, 'newCredentials': newCredentials}), 200, {"Content-type": "application/json"}

@server.route("/api/secure/users/<username>", methods=["DELETE"])
def delete_user_with_roles(request, username):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    
    if username == 'admin':
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    groups = auth.get_users_with_groups()[username];
    if not auth.remove_user_with_groups(username):
        return json.dumps({'message': 'Conflict'}), 409, {"Content-type": "application/json"}
    newCredentials = auth.refresh_token(user)
    return json.dumps({'username': username, 'groups': groups, 'newCredentials': newCredentials}), 200, {"Content-type": "application/json"}

@server.route("/api/wifi", methods=["PATCH"])
def wifi_conf(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    
    old = load_json('net.json')
    new = old.copy()
    new.update(request.data)
    accepted = old.copy()
    accepted['ssid'] = new['ssid']
    accepted['pass'] = new['pass']
    accepted['ap-ssid'] = new['ap-ssid']
    accepted['ap-pass'] = new['ap-pass']
    if (save_json('net.json', accepted)):
        newCredentials = auth.refresh_token(user)
        return json.dumps({'net': accepted, "newCredentials": newCredentials}), 202, {"Content-type": "application/json"}
    else:
        return json.dumps({'message': 'Internal Server Error'}), 500, {"Content-type": "application/json"}

@server.route("/api/pixelprograms", methods=["PUT", "PATCH"])
def change_pixelprograms(request):
    user = auth.authenticate(request)
    if not user:
        return json.dumps({"message": "Unauthorized"}), 401, {"Content-type": "application/json"}
    if not auth.authorize(user, ["admin", "designer"]):
        return json.dumps({"message": "Forbidden"}), 403, {"Content-type": "application/json"}
    
    old = load_json('pixelprograms.json')
    pixelprograms = request.data
    new = pixelprograms
    if (request.method == "PATCH"):
        new = old.copy()
        new.extend(pixelprograms)
    if (save_json('pixelprograms.json', new)):
        new_credentials = auth.refresh_token(user)
        return json.dumps({'before': old, 'after': new, 'newCredentials': new_credentials}), 202, {"Content-type": "application/json"}
    else:
        return json.dumps({'message': 'Internal Server Error'}), 500, {"Content-type": "application/json"}

@server.route("/api/data", methods=["GET"])
def get_data(request):
    return json.dumps(load_json('data.json')), 200, {"Content-type": "application/json"}

@server.route("/api/current-state", methods=["GET"])
def get_current_state(request):
    return json.dumps(driver.current_state()), 200, {"Content-type": "application/json"}

@server.route("/api/pixelprograms", methods=["GET"])
def get_pixelprograms(request):
    return json.dumps(load_json('pixelprograms.json')), 200, {"Content-type": "application/json"}
    
@server.catchall()
def catchall(request):
    return json.dumps({"massage": "Page not exists"}), 404, {"Content-type": "application/json"}

