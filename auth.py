from phew import logging
import json
import ubinascii

from utils import load_json, save_json

def apply_auth_headers(request):
    """
    Dekoduje nagłówek 'Authorization: Basic ...' i wstrzykuje pola
    'user' i 'token' do obiektu request.headers.
    """
    auth = request.headers.get("authorization", None)
    if auth and auth.startswith("Basic "):
        try:
            # Pomiń "Basic " i dekoduj Base64
            decoded = ubinascii.a2b_base64(auth[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
            
            request.headers["user"] = username
            request.headers["token"] = password
            request.headers["pass"] = password
            return True
        except Exception as e:
            logging.debug(f"Auth error: {e}")
    return False

def add_user_to_groups(username, group_names):
    """Przypisuje użytkownika do konkretnej roli w groups.json."""
    groups = load_json('groups.json')
    for group_name in group_names:
        if group_name not in groups:
            groups[group_name] = []
            
        if username not in groups[group_name]:
            groups[group_name].append(username)
    if not save_json('groups.json', groups):
        return False
    logging.info(f"> User '{username}' assigned to '{group_names}'")
    return True

def remove_user_from_all_groups(username):
    """
    Usuwa użytkownika ze wszystkich ról w groups.json.
    """
    groups = load_json('groups.json')
    changed = False

    for role in groups:
        if username in groups[role]:
            groups[role].remove(username)
            changed = True

    if changed:
        if save_json('groups.json', groups):
            logging.info(f"> User '{username}' removed from all groups")
            return True
    return False

def create_user_with_groups(username, password, group_names):
    users = load_json('users.json')
    if username in users:
        return False
    if (len(password) < 7):
        return False
    users[username] = {'pass': password, 'token': generate_token()}
    logging.info(f"> User '{username}' has been created")
    if not save_json('users.json', users):
        return False
    add_user_to_groups(username, group_names)
    return True

def remove_user_with_groups(username):
    if username == 'admin':
        return False
    users = load_json('users.json')
    if username not in users:
        return False
    del users[username]
    if not save_json('users.json', users):
        return False
    remove_user_from_all_groups(username)
    logging.info(f"> User '{username}' and roles removed")
    return True

def ensure_default_setup():
    """Gwarantuje istnienie ról i konto admina przy starcie."""
    users = load_json('users.json')
    groups = load_json('groups.json')
    roles = ['admin', 'designer', 'editor']
    changed = False

    for role in roles:
        if role not in groups:
            groups[role] = []
            changed = True
            
    if 'admin' not in users:
        create_user('admin', 'administrator', ['admin'])

    if 'admin' not in groups['admin']:
        groups['admin'].append('admin')
        changed = True

    if changed:
        save_json('groups.json', groups)
        logging.info("> Default RBAC structure initialized")

def authenticate(request):
    """
    KROK 1: Uwierzytelnianie (Kim jesteś?)
    Zwraca username jeśli token jest poprawny, w przeciwnym razie None.
    """
    if 'user' not in request.headers:
        apply_auth_headers(request)

    user = request.headers.get('user')
    token = request.headers.get('token')

    if not user or not token:
        return None

    users = load_json('users.json')
    if user in users:
        # Sprawdzamy token lub hasło (np. przy pierwszym logowaniu)
        if users[user].get('token') == token:
            return user
    
    return None

def authorize(username, allowed_groups):
    """
    KROK 2: Autoryzacja (Co możesz zrobić?)
    Zwraca True jeśli użytkownik należy do którejś z wymaganych grup.
    """
    if not username:
        return False

    groups = load_json('groups.json')
    for group in allowed_groups:
        if username in groups.get(group, []):
            return True
    return False

def refresh_token(username):
    users = load_json('users.json')
    if username not in users:
        return {'message': f'User {username} not exists'}
    
    users[username]['token'] = generate_token()
    if (save_json('users.json', users)):
        logging.info(f'> refresh token for {username}')
        return {"token": users[username]['token'], "user": username}
    else:
        logging.debug(f'> cannot refresh token for {username}')
        return {'message': 'Cannot generate access token. Try again.'}
    
def generate_token():
    import ubinascii
    import os
    return ubinascii.b2a_base64(os.urandom(32)).decode().strip()

def get_users_with_groups():
    """
    Zwraca słownik, gdzie kluczem jest nazwa użytkownika, 
    a wartością lista grup, do których należy.
    """
    groups = load_json('groups.json')
    users_mapping = {}

    for group_name, users_list in groups.items():
        for user in users_list:
            if user not in users_mapping:
                users_mapping[user] = []
            users_mapping[user].append(group_name)
            
    return users_mapping