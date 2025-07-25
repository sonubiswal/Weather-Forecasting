from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk
import requests

def data_get():
    city = city_name.get()
    try:
        response = requests.get("your api id")
        response.raise_for_status()
        data = response.json()

        weather_main = data["weather"][0]["main"]
        description = data["weather"][0]["description"]
        temp = str(int(data["main"]["temp"] - 273.15)) + "°C"
        pressure = str(data["main"]["pressure"]) + " hPa"
        wind_speed = str(data["wind"]["speed"]) + " m/s"
        humidity = str(data["main"]["humidity"]) + "%"
        
        w_label1.config(text=weather_main)
        temp_label1.config(text=temp)
        pr_label1.config(text=pressure)
        wind_label1.config(text=wind_speed)
        humidity_label1.config(text=humidity)
        
        icon_code = data["weather"][0]["icon"]
        icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
        image = Image.open(requests.get(icon_url, stream=True).raw)
        resized_image = image.resize((200, 200))
        icon = ImageTk.PhotoImage(resized_image)
        
        wd_label1.config(text=description, image=icon, compound='top', padx=20, pady=10)
        wd_label1.image = icon

        # Change background image based on weather description
        if "rain" in description.lower():
            bg_img = PhotoImage(file="C:\\Users\\Sumit Biswal\\OneDrive\\Desktop\\Projects\\my_venv\\project_1\\image\\back.png")  # Replace with your image path
        elif "clear" in description.lower():
            bg_img = PhotoImage(file="C:\\Users\\Sumit Biswal\\OneDrive\\Desktop\\Projects\\my_venv\\project_1\\image\\clear sky.png")  # Replace with your image path
        elif "cloud" in description.lower():
            bg_img = PhotoImage(file="C:\\Users\\Sumit Biswal\\OneDrive\\Desktop\\Projects\\my_venv\\project_1\\image\\cloude.png")  # Replace with your image path
        elif "snow" in description.lower():
            bg_img = PhotoImage(file="C:\\Users\\Sumit Biswal\\OneDrive\\Desktop\\Projects\\my_venv\\project_1\\image\\snow.png")  # Replace with your image path
        elif "mist" in description.lower() or "fog" in description.lower():
            bg_img = PhotoImage(file="C:\\Users\\Sumit Biswal\\OneDrive\\Desktop\\Projects\\my_venv\\project_1\\image\\mist.png")  # Replace with your image path
        else:
            bg_img = PhotoImage(file="C:\\Users\\Sumit Biswal\\OneDrive\\Desktop\\Projects\\my_venv\\project_1\\image\\pg.png")  # Replace with your image path
        
        bg_label.config(image=bg_img)
        bg_label.image = bg_img  # Keep a reference to avoid garbage collection

    except requests.exceptions.RequestException:
        w_label1.config(text="Error")
        temp_label1.config(text="N/A")
        pr_label1.config(text="N/A")
        wind_label1.config(text="N/A")
        humidity_label1.config(text="N/A")
        wd_label1.config(text="Unable to fetch data", image='', padx=20, pady=10)

    except KeyError:
        w_label1.config(text="Not Found")
        temp_label1.config(text="N/A")
        pr_label1.config(text="N/A")
        wind_label1.config(text="N/A")
        humidity_label1.config(text="N/A")
        wd_label1.config(text="City not found", image='', padx=20, pady=10)

window = Tk()
window.title("Weather Forecast System")

# Initial background image
bg_img = PhotoImage(file="C:\\Users\\OneDrive\\Desktop\\Projects\\my_venv\\image\\pg.png")  
bg_label = Label(window, image=bg_img)
bg_label.pack(fill=BOTH, expand=True)

head_label = Label(window, text="Weather Forecast System", bg='#2C3E50', fg="#ECF0F1", highlightbackground="black", highlightthickness=1, font=("Times New Roman", 30, "bold"), relief=RAISED)
head_label.place(x=398, y=40, height=60, width=800)

List_name = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
             "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", 
             "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", 
             "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
             "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", 
             "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", 
             "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu", "Lakshadweep", 
             "National Capital Territory of Delhi", "Puducherry"]

city_name = StringVar()
com = ttk.Combobox(window, values=List_name, font=("Times New Roman", 24), textvariable=city_name)
com.place(x=444, y=140, height=60, width=520)

wd_label = Label(window, text="Weather Description", highlightbackground="black", highlightthickness=1, bg='#34495E', fg='#ECF0F1', font=("Times New Roman", 24), relief=RIDGE)
wd_label.place(x=290, y=280, height=60, width=360)
wd_label1 = Label(window, text="", highlightbackground="black", highlightthickness=1, bg='#4682B4', fg='#ECF0F1', font=("Times New Roman", 26), compound='top', padx=20, pady=10, relief=RIDGE)
wd_label1.place(x=265, y=360, height=260, width=410)

w_label = Label(window, text="Weather Climate", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
w_label.place(x=700, y=250, height=60, width=290)
w_label1 = Label(window, text="", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
w_label1.place(x=1010, y=250, height=60, width=290)

temp_label = Label(window, text="Temperature", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
temp_label.place(x=700, y=330, height=60, width=290)
temp_label1 = Label(window, text="", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
temp_label1.place(x=1010, y=330, height=60, width=290)

pr_label = Label(window, text="Pressure", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
pr_label.place(x=700, y=420, height=60, width=290)
pr_label1 = Label(window, text="", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
pr_label1.place(x=1010, y=420, height=60, width=290)

wind_label = Label(window, text="Wind Speed", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
wind_label.place(x=700, y=500, height=60, width=290)
wind_label1 = Label(window, text="", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
wind_label1.place(x=1010, y=500, height=60, width=290)

humidity_label = Label(window, text="Humidity", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
humidity_label.place(x=700, y=580, height=60, width=290)
humidity_label1 = Label(window, text="", highlightbackground="black", highlightthickness=1, bg='#2C3E50', fg='#ECF0F1', font=("Times New Roman", 24), relief=RAISED)
humidity_label1.place(x=1010, y=580, height=60, width=290)

click_button = Button(window, text="Check", font=("Times New Roman", 24, "bold"), bg='#E74C3C', fg='#FFFFFF', command=data_get)
click_button.place(x=990, y=140, height=60, width=150)

window.state('zoomed')
window.mainloop()
