# Waterflow Pixel Unit

A firmware project for a "flowing water" LED effect controller built for **Raspberry Pi Pico 2 W**. The application is written for MicroPython and exposes a REST API for device configuration, user management, and diagnostics.

> ⚠️ **Important (production configuration):** before running on a target device, you **must change values in `config.py`**, especially:
> - `secured['secure']`
> - `device['uuid']`
>
> The current values in this repository are **examples** and **must not remain unchanged** on the final device.

---

## 1. Hardware target

This project is intended to be installed on:

- **Raspberry Pi Pico 2 W**
- together with a **dedicated expansion board** (I/O and power handling for LED strip / actuators).

Default GPIO pins are `sensor=18`, `dout=19`, and `off=20`. They can be changed in `gpio.json` or through the `api/secure/gpio` endpoint. Reading this endpoint is public; changing values requires an administrator. Hardware compatibility with the target expansion module should be verified after every GPIO change.

---

## 2. Architecture overview

- `main.py` starts:
  - the LED controller task (`WaterflowDriver.run()`)
  - the HTTP server (`phew.server.run()`).
- `myhttp.py`:
  - connects to Wi‑Fi (or starts AP fallback mode),
  - registers REST API endpoints,
  - handles authentication/authorization.
- `waterflowdriver.py` implements LED strip runtime logic with dependencies on:
  - time schedule,
  - sensor state,
  - configuration loaded from JSON files.

---

## 3. Required runtime configuration files

The project reads and writes data in JSON files stored on the device.

### 3.1 `config.py`
A static file with device metadata and security settings:

- `device` – device metadata (`uuid`, app name, etc.),
- `secured` – security section (`secure`, `api-key`).

**Before deployment:**
- set your own `device['uuid']`,
- set your own `secured['secure']` (recommended: also update `secured['api-key']`).

### 3.2 JSON files used by the app
- `net.json` – Wi‑Fi/AP configuration:
  - `ssid`, `pass`, `ap-ssid`, `ap-pass`
- `users.json` – users, passwords, tokens
- `groups.json` – role mapping (`admin`, `designer`, `editor`)
- `data.json` – device runtime configuration (e.g. `pixelProgram`, `brightness`, `stepTime`, `onTime`, `offTime`, `on`, `nol`, ...)
- `gpio.json` – GPIO port numbers used by the device (`dout`, `sensor`, `off`)
- `pixelprograms.json` – list of pixel animation programs
- log file (`logging.log_file`, depending on `phew.logging` setup)

> On first startup, the backend ensures a default RBAC structure (roles + `admin` account).


### 3.3 `gpio.json`
GPIO configuration is loaded from `gpio.json` at startup and refreshed by the runtime driver. Default content:

```json
{
  "dout": 19,
  "sensor": 18,
  "off": 20
}
```

Fields:
- `dout` – GPIO number for the LED strip data line,
- `sensor` – GPIO number for the input sensor (`Pin.IN`, `Pin.PULL_UP`),
- `off` – GPIO number for the output used when the controller is inactive.

Accepted values are integers from `0` to `28`. Invalid or missing values are replaced by defaults when the file is normalized.

---

## 4. API authentication and authorization

### 4.1 Access model
- Authentication: user + token passed in request headers.
- Authorization: role/group based (`admin`, `editor`, `designer`).

### 4.2 How to log in
Login endpoint:
- `POST /api/secure/auth`

Credentials handling:
- API accepts Basic Auth (`Authorization: Basic base64(user:pass)`),
- on successful login it returns a fresh token.

### 4.3 How to call protected endpoints
For protected endpoints send headers:
- `user: <username>`
- `token: <token_from_login>`

Many endpoints also refresh token and return `newCredentials` in response.

### 4.4 Administrative exception
- `POST /api/secure/admin/reset` requires header:
  - `secure: <value_of_config.secured['secure']>`

---

## 5. REST API – detailed reference

Below is a complete endpoint list based on the current backend code.

## 5.1 Public endpoints

### `GET /api/info`
Returns device metadata (`config.device`).

**200 OK (JSON)**
```json
{
  "uuid": "...",
  "manufacturer": "Raspberry Pi",
  "product-name": "Pico 2 W",
  "application-name": "Waterflow Pixel Unit"
}
```

---

### `GET /api/logs`
Returns log entries as an array of text lines.

**200 OK (JSON)**
```json
["line 1", "line 2", "..."]
```

---

### `GET /api/data`
Returns current runtime configuration from `data.json`.

**200 OK (JSON)** – schema depends on current file content.

---

### `GET /api/current-state`
Returns current driver state (`driver.current_state()`), including current action (`extending`/`reducing`) and runtime parameters.

**200 OK (JSON)** – dynamic structure (current state + driver object fields).

---

### `GET /api/pixelprograms`
Returns list of pixel programs from `pixelprograms.json`.

**200 OK (JSON)**
```json
[
  [[255,0,0],[0,0,255]],
  [[0,255,0],[0,0,0]]
]
```

---

## 5.2 Protected endpoints (token / role)

### `DELETE /api/logs`
Clears log file.

- Required role: `admin`

**200 OK**
```json
{
  "logs": ["...previous logs..."],
  "newCredentials": {"user":"...","token":"..."}
}
```

**Errors:** `401`, `403`, `500`.

---

### `POST /api/restart`
Starts countdown to soft restart (`machine.soft_reset()`).

- Required role: `admin` or `editor`

**200 OK**
```json
{
  "restartCountdown": 10,
  "newCredentials": {"user":"...","token":"..."}
}
```

---

### `PATCH /api/secure/pass`
Changes password for currently authenticated user.

- Minimum password length: 7

**Body (JSON)**
```json
{"pass":"NewPassword123"}
```

**202 Accepted**
```json
{
  "username":"admin",
  "newCredentials":{"user":"admin","token":"..."}
}
```

**Errors:** `401`, `406`, `500`.

---

### `PUT /api/data`
Replaces full `data.json` configuration.

### `PATCH /api/data`
Partially updates `data.json` configuration.

- Required role: `admin` or `editor`
- If `nol` is missing, API sets `nol = 3`.

**202 Accepted**
```json
{
  "before": {"...": "..."},
  "after": {"...": "..."},
  "newCredentials": {"user":"...","token":"..."}
}
```

---

### `PATCH /api/wifi`
Updates network configuration (`net.json`).

- Required role: `admin`
- Accepted fields: `ssid`, `pass`, `ap-ssid`, `ap-pass`

**Body (JSON)**
```json
{
  "ssid":"MyNetwork",
  "pass":"MyPassword",
  "ap-ssid":"Waterflow-Setup",
  "ap-pass":"SetupPass123"
}
```

**202 Accepted**
```json
{
  "net": {
    "ssid": "...",
    "pass": "...",
    "ap-ssid": "...",
    "ap-pass": "..."
  },
  "newCredentials": {"user":"...","token":"..."}
}
```

---

### `PUT /api/pixelprograms`
Overwrites full list of pixel programs.

### `PATCH /api/pixelprograms`
Appends programs to existing list.

- Required role: `admin` or `designer`

**202 Accepted** – returns `before`, `after`, `newCredentials`.

---

### `GET /api/secure/admin`
Returns `secured` section from `config.py`.

- Required role: `admin`

**200 OK**
```json
{
  "secure": {"secure":"...","api-key":"..."},
  "newCredentials": {"user":"...","token":"..."}
}
```

---


### `GET /api/secure/gpio`
Returns current GPIO configuration from `gpio.json`. This read endpoint is public and does not refresh or return an access token.

**200 OK**
```json
{"dout":19,"sensor":18,"off":20}
```

---

### `PUT /api/secure/gpio`
Replaces full GPIO configuration.

### `PATCH /api/secure/gpio`
Partially updates GPIO configuration.

- Required role: `admin`
- Accepted fields: `dout`, `sensor`, `off`
- Accepted values: integers from `0` to `28`
- The backend saves normalized values to `gpio.json` and applies changed pins to the running driver.

**Body (JSON)**
```json
{
  "dout": 19,
  "sensor": 18,
  "off": 20
}
```

**202 Accepted**
```json
{
  "before": {"dout":19,"sensor":18,"off":20},
  "after": {"dout":21,"sensor":18,"off":20},
  "newCredentials": {"user":"admin","token":"..."}
}
```

**Errors:** `400`, `401`, `403`, `500`.

---

### `GET /api/secure/users`
Returns mapping of users to roles.

- Required role: `admin`

**200 OK**
```json
{
  "users": {
    "admin": ["admin"],
    "operator": ["editor"]
  },
  "newCredentials": {"user":"...","token":"..."}
}
```

---

### `POST /api/secure/users`
Creates user and assigns groups.

- Required role: `admin`

**Body (JSON)**
```json
{
  "user":"operator",
  "pass":"StrongPassword123",
  "groups":["editor"]
}
```

**200 OK**
```json
{
  "username":"operator",
  "groups":["editor"],
  "newCredentials":{"user":"admin","token":"..."}
}
```

**Errors:** `400`, `401`, `403`, `409`.

---

### `DELETE /api/secure/users/<username>`
Deletes user (except `admin`) and related roles.

- Required role: `admin`

**200 OK**
```json
{
  "username":"operator",
  "groups":["editor"],
  "newCredentials":{"user":"admin","token":"..."}
}
```

---

## 5.3 “secure header” endpoint

### `POST /api/secure/admin/reset`
Emergency reset of `admin` account password.

**Required headers**
- `secure: <config.secured['secure']>`

**Body (JSON)**
```json
{"pass":"NewAdminPassword"}
```

**Response codes**
- `202 Accepted` – password changed
- `400 Bad Request` – missing `pass`
- `401 Unauthorized` – wrong/missing `secure`
- `406 Not Acceptable` – password too short
- `500 Internal Server Error` – save error

---

## 5.4 Login

### `POST /api/secure/auth`
User login endpoint.

**Header**
- `Authorization: Basic base64(user:pass)`

**200 OK**
```json
{"token":"...","user":"admin"}
```

**401 Unauthorized** – invalid credentials.

---

## 5.5 Fallback endpoint

For non-existing paths backend returns:
- `404`
- body: `{"massage": "Page not exists"}`

---

## 6. Quick `curl` examples

### Login
```bash
curl -X POST http://<DEVICE_IP>/api/secure/auth \
  -H "Authorization: Basic $(printf 'admin:administrator' | base64)"
```

### Public data read
```bash
curl http://<DEVICE_IP>/api/current-state
```

### Configuration update (PATCH /api/data)
```bash
curl -X PATCH http://<DEVICE_IP>/api/data \
  -H "Content-Type: application/json" \
  -H "user: admin" \
  -H "token: <TOKEN>" \
  -d '{"brightness":128,"on":true}'
```


### GPIO configuration update (PATCH /api/secure/gpio)
```bash
curl -X PATCH http://<DEVICE_IP>/api/secure/gpio \
  -H "Content-Type: application/json" \
  -H "user: admin" \
  -H "token: <TOKEN>" \
  -d '{"dout":21}'
```

### Admin password reset with `secure`
```bash
curl -X POST http://<DEVICE_IP>/api/secure/admin/reset \
  -H "Content-Type: application/json" \
  -H "secure: <CONFIG_SECURED_SECURE>" \
  -d '{"pass":"NewAdminPassword"}'
```

---

## 7. USB installation on Raspberry Pi Pico 2 W

A practical and safe deployment path:

1. **Flash MicroPython UF2**
   - Disconnect Pico from USB.
   - Hold `BOOTSEL` and connect USB.
   - Pico appears as `RPI-RP2` mass storage.
   - Copy MicroPython `.uf2` firmware for Pico 2 W.

2. **Copy project files to device**
   - Most convenient via **Thonny** (Interpreter: MicroPython (Raspberry Pi Pico)).
   - Copy to device storage:
     - `main.py`, `myhttp.py`, `waterflowdriver.py`, `waterflowpixel.py`, `auth.py`, `utils.py`, `config.py`, `ktime.py`, `neopixel.py`
     - `lib/` folder
     - required JSON files (`net.json`, `users.json`, `groups.json`, `data.json`, `gpio.json`, `pixelprograms.json`) configured for your environment.

3. **Adjust configuration before first run**
   - Set unique values in `config.py`, especially:
     - `secured['secure']`
     - `device['uuid']`
   - Set Wi‑Fi/AP credentials in `net.json`.
   - Verify GPIO numbers in `gpio.json` for your expansion board.

4. **Restart and test API**
   - Restart device (soft/hard reset).
   - Read IP from serial/log output.
   - Verify `GET /api/info` and `POST /api/secure/auth`.

---

## 8. Security best practices

- Do not use example secrets or UUIDs in production.
- Use strong user passwords (minimum 7 chars required; significantly longer recommended).
- Restrict network access to API (VLAN/firewall).
- Treat tokens as sensitive secrets (API rotates them frequently).

---

## 9. Project status

This repository contains MicroPython application firmware for a Pico 2 W based LED controller with a REST API for remote management.
