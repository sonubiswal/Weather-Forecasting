# Weather-Forecasting
   A simple Python Tkinter app that shows real-time weather using OpenWeatherMap API, with icons based on weather conditions like sunny, rainy, or cloudy and many     more.

Overview:
   This is a simple desktop application built using Python's Tkinter library to display the weather forecast for different states of India. The app fetches real-      time weather data from the OpenWeatherMap API and presents it in a clean and user-friendly interface.

Features:
   Select a city/state from a dropdown list.
   View current weather conditions including temperature, humidity, wind speed, pressure, and a brief description.
   Weather icon and background image change dynamically based on the weather condition.
   Error handling for invalid city names or API request failures.

How It Works:
   The app uses the OpenWeatherMap API to get weather data. When you select a city and click the "Check" button, it sends a request to the API, retrieves the          weather data in JSON format, and then updates the UI labels with the relevant information. It also downloads the weather icon and changes the background image      to match the current weather condition.

Requirements:
   Python 3.x
   Tkinter (usually comes pre-installed with Python)
   Pillow (you can install it using pip install pillow)
   Requests (you can install it using pip install requests)

How to Use:
   Clone or download this repository.
   Replace "your api id" in the code with your OpenWeatherMap API key.
   Run the Python script.
   Select a city from the dropdown menu.
   Click the "Check" button to see the current weather data.

Notes:
   Make sure you have an active internet connection for the app to fetch the data.
   Background images need to be available in the specified file paths or update the paths according to your system.
   The temperature is displayed in Celsius.
