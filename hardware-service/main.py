"""
main.py

This file implements a very small web-controlled hardware interface:

Browser (HTML + JS)  -->  FastAPI web server (this file)  -->  Serial  -->  Arduino

- The browser shows a simple page with two buttons: "LED ON" and "LED OFF".
- When you click a button, the browser sends an HTTP POST request to /api/led with JSON.
- FastAPI receives the request, parses the JSON into a LedCommand object, and sends a serial
  command to the Arduino.
- The Arduino sketch reads the serial command and turns the LED on or off.

This is your "mini remote control system" MVP.
"""

# ----- Imports -----
# These bring in external libraries / modules that provide functionality we need.

import serial  # From the pyserial package. Provides Serial class for talking over USB/serial.

from fastapi import FastAPI  # FastAPI is the web framework: it handles HTTP requests and routes.
from fastapi.responses import HTMLResponse  # Used to tell FastAPI "this response is raw HTML, not JSON".

from pydantic import BaseModel
# Pydantic provides BaseModel, which we use to define data models (schemas) for request bodies.
# FastAPI uses these models to parse and validate incoming JSON automatically.


# ----- Serial configuration -----
# These variables describe how to connect to the Arduino over USB serial.

# Path to the serial device for your Arduino.
# This MUST match what you see when you run: ls /dev/tty.usb*
# Example: "/dev/tty.usbmodem11202"
SERIAL_PORT = "/dev/tty.usbmodem11202"  # <-- use the same value you already found

# Baud rate must match Serial.begin(BAUD_RATE) in your Arduino sketch.
BAUD_RATE = 115200


# ----- FastAPI application object -----
# This creates the web application instance.
# Think of this like the "server" object that will hold all your routes/endpoints.

app = FastAPI()
# When uvicorn runs "main:app", this is the 'app' it is looking for.


# ----- Serial port object -----
# Open the serial connection to the Arduino when this module is imported.
# serial.Serial(...) returns an object that represents an open serial port.
# We store it in a global variable 'ser' so route handlers can use it.

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
# Arguments:
# - SERIAL_PORT: which device to open (your Arduino)
# - BAUD_RATE: speed of communication (must match Arduino)
# - timeout=1: read calls will wait up to 1 second before giving up


# ----- Data model for the LED command -----
# This defines the "shape" of the JSON we expect in POST /api/led.
# Example JSON body from the browser: { "state": 1 }

class LedCommand(BaseModel):
    """
    LedCommand represents the data we expect in the JSON body for /api/led.

    Fields:
    - state: int
        0 means "LED off"
        1 (or any non-zero) means "LED on"

    FastAPI uses this model to:
    - Parse incoming JSON into a Python object
    - Validate that 'state' is an integer
    """
    state: int  # type annotation (like 'int state;' in C++ but Python-style)


# ----- API endpoint: POST /api/led -----
# This is the core of the control API.
# When the browser calls fetch('/api/led', { method: 'POST', body: JSON }),
# FastAPI will trigger this function.

@app.post("/api/led")
def set_led(cmd: LedCommand):
    """
    Handle an HTTP POST request to /api/led.

    Flow:
    1. FastAPI parses the JSON body into a LedCommand object, passed in as 'cmd'.
       - For example, JSON { "state": 1 } becomes LedCommand(state=1).
    2. We sanitize that value into either 0 or 1.
    3. We build a command string like "LED 1\n".
    4. We send that string over the serial port to the Arduino.
    5. We return a small JSON response indicating what we sent.
    """

    # Ternary expression in Python:
    # "state = 1 if cmd.state else 0" is similar to "state = cmd.state ? 1 : 0;" in C++.
    #
    # Explanation:
    # - In Python, 0 is "falsey" and any non-zero integer is "truthy".
    # - If cmd.state is 0 --> state becomes 0
    # - If cmd.state is non-zero --> state becomes 1
    #
    # This ensures we always send 0 or 1 to the Arduino, even if the client sent something weird.
    state = 1 if cmd.state else 0

    # Build the serial command string.
    # f"..." is a formatted string (f-string).
    # {state} gets replaced with the value of the 'state' variable.
    #
    # Example: if state == 1, command_str == "LED 1\n"
    # The newline '\n' is used so Arduino can read a full line with readStringUntil('\n').
    command_str = f"LED {state}\n"

    # Convert the Python string (Unicode) into bytes using UTF-8 encoding.
    # Serial writes bytes, not high-level strings.
    # This has nothing to do with Arduino pin numbers; it's just text encoding.
    ser.write(command_str.encode("utf-8"))

    # Flush ensures the output buffer is emptied and the data is actually sent out.
    # It does NOT reset a pin; it's about serial I/O buffering.
    ser.flush()

    # Return a JSON response to the client (browser or any HTTP client).
    # FastAPI automatically converts this Python dict into JSON.
    #
    # command_str.strip() removes leading/trailing whitespace like the trailing '\n',
    # so the 'sent' string looks nicer in the response.
    return {
        "status": "ok",
        "sent": command_str.strip()
    }


# ----- API endpoint: GET / -----
# This serves the main HTML page with the two buttons.
# The browser loads this when you go to http://127.0.0.1:8000/

@app.get("/", response_class=HTMLResponse)
def index():
    """
    Serve a very simple HTML page that:
    - Shows a title
    - Has two buttons: "LED ON" and "LED OFF"
    - Each button calls a JavaScript function 'setLed(state)' which sends a POST request to /api/led

    This function returns a raw HTML string. Using response_class=HTMLResponse tells FastAPI
    to send it as text/html so the browser renders it as a page instead of showing the raw text.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Remote Rig - LED Control</title>
    </head>
    <body>
      <h1>Remote Rig - LED Control</h1>

      <!-- Two simple buttons that call a JavaScript function when clicked -->
      <button onclick="setLed(1)">LED ON</button>
      <button onclick="setLed(0)">LED OFF</button>

      <script>
        // setLed is a client-side (browser) function written in JavaScript.
        // It sends an HTTP POST request to /api/led with a JSON body { state: <value> }.
        async function setLed(state) {
          // fetch() is the modern API for making HTTP requests from JavaScript.
          await fetch('/api/led', {
            method: 'POST',                         // HTTP method
            headers: { 'Content-Type': 'application/json' }, // Tell the server we are sending JSON
            body: JSON.stringify({ state })         // Convert JS object { state: state } to JSON text
          });
          // We are ignoring the response here, but we could read it if we wanted
          // (for example to show a status message on the page).
        }
      </script>
    </body>
    </html>
    """

