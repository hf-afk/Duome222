# Install dependencies (Uncomment these lines if running in Colab)
# !apt-get update
# !apt install chromium-chromedriver
# !pip install selenium pandas matplotlib beautifulsoup4 pytz pillow tzlocal

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
from tzlocal import get_localzone
from PIL import Image
import base64
import re
import os

def fetch_profile_name(driver, wait, username):
    """
    Refreshes the page and attempts to fetch the profile name.
    Returns the profile name if successful, otherwise None.
    """
    try:
        # Wait for the refresh button to be clickable and refresh data
        refresh_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"span[data-id='{username}']"))
        )
        print("Refreshing data...")
        refresh_button.click()

        # Wait for the page to refresh
        WebDriverWait(driver, 10).until(EC.staleness_of(refresh_button))
        print("Data refreshed.")

        # Try to scrape profile name
        profile_name_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h3 span.json-name"))
        )
        return profile_name_element.text.strip()
    except Exception as e:
        print("❌ Wrong username, please try again.")
        return None

def scrape_duolingo_progress(username):
    """
    Main function to scrape Duolingo progress for the given username.
    Handles invalid usernames gracefully and ensures the driver is closed properly.
    """
    url = f"https://duome.eu/{username}"

    # Configure Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)
    profile_found = False  # Flag to track if the profile is valid

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        # Fetch the profile name
        profile_name = fetch_profile_name(driver, wait, username)
        if not profile_name:
            return  # Exit the function if the profile is not found

        profile_found = True  # Profile is valid
        print(f"Profile name: {profile_name}")

        # Fetch the UTC offset
        header_element = wait.until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/h4/span"))
        )
        utc_offset_text = header_element.text  # e.g., " · UTC+5:30"
        print(f"User's Profile TimeZone: {utc_offset_text}")

        # Extract UTC offset
        offset_match = re.search(r"UTC([+-]?\d+)(?::(\d+))?", utc_offset_text)
        hours = int(offset_match.group(1)) if offset_match else 0
        minutes = int(offset_match.group(2) or 0) if offset_match else 0
        profile_utc_offset = timedelta(hours=hours, minutes=minutes)

        # Detect local timezone
        local_tz = get_localzone()

        # Click the "Raw" button
        raw_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.q.raw"))
        )
        print("Opening raw data...")
        raw_button.click()

        # Wait for the raw data section to appear
        raw_data_element = wait.until(
            EC.presence_of_element_located((By.ID, "raw"))
        )
        raw_html = raw_data_element.get_attribute("innerHTML")

        # Parse the raw HTML data using BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")
        xp_entries = soup.find_all("li")

        # Extract date, time, and XP gained
        data = []
        for entry in xp_entries:
            text = entry.get_text(strip=True)
            if "XP" in text:
                parts = text.split("·")
                if len(parts) >= 2:
                    datetime_part = parts[0].strip()
                    xp_part = parts[1].strip()

                    # Extract numeric XP value using regex
                    xp_match = re.search(r"(\d+)\s*XP", xp_part)
                    if xp_match:
                        xp = int(xp_match.group(1))  # Extract the number part

                        # Split datetime into date and time
                        datetime_split = datetime_part.split(" ")
                        if len(datetime_split) == 2:
                            date = datetime_split[0]
                            time = datetime_split[1]

                            # Convert profile time to UTC
                            dt_profile = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
                            dt_utc = dt_profile - profile_utc_offset

                            # Convert UTC to local timezone
                            dt_local = dt_utc.replace(tzinfo=pytz.utc).astimezone(local_tz)

                            data.append({
                                "date": dt_local.strftime("%d-%m-%Y"),  # Convert to dd-mm-yyyy format
                                "time": dt_local.strftime("%H:%M:%S"),
                                "xp": xp
                            })

        # Create a DataFrame from the data
        df = pd.DataFrame(data)
        print("Extracted Data:")
        print(df)

        # Save DataFrame to CSV
        csv_filename = f"{profile_name}_progress.csv"
        df.to_csv(csv_filename, index=False)
        print(f"Data saved to {csv_filename}")

        # Sort data by date and time in ascending order
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format="%d-%m-%Y %H:%M:%S")
        df.sort_values('datetime', inplace=True)
        df.reset_index(drop=True, inplace=True)

        # Visualization
        row_count = len(df)
        plt.figure(figsize=(12, max(4, row_count // 3)))  # Adjust height dynamically

        # Plot horizontal bars
        plt.barh(df.index, df['xp'], color='#22FF44', edgecolor='black')

        # Add XP labels on bars
        for index, value in enumerate(df['xp']):
            plt.text(value + 5, index, str(value), va='center', fontsize=9, color='black')

        # Set y-axis labels to show lesson times (ascending order)
        plt.yticks(df.index, df['date'] + ' ' + df['time'], fontsize=10)

        # Add labels and title
        plt.xlabel("XP Gained", fontsize=14)
        plt.ylabel("Lesson (Date & Time)", fontsize=14)
        plt.title(f"{profile_name}'s Progress Visualization", fontsize=16)
        plt.tight_layout(pad=2.0)

        # Save and show the plot
        plot_filename = f"{profile_name}_progress_plot.png"
        plt.savefig(plot_filename)
        print(f"Plot saved to {plot_filename}")
        plt.show()

        # Scrape and save the progress history canvas image
        canvas_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#myCanvas"))
    )
        canvas_data_url = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas_element
    )
        canvas_image_data = base64.b64decode(canvas_data_url)
        canvas_filename = f"{profile_name}_history.png"
        with open(canvas_filename, "wb") as f:
            f.write(canvas_image_data)
        print(f"Canvas image saved to {canvas_filename}")

    finally:
        if profile_found:
            print("Closing driver...")
        driver.quit()

# User-specified parameters
USERNAME = input("Enter the Duolingo username of the user you want to visualize progress for: ").strip()
scrape_duolingo_progress(USERNAME)
