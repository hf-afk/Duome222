# Import necessary libraries
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from tzlocal import get_localzone
import re
import base64
from io import BytesIO

# Function to scrape Duolingo progress
def scrape_duolingo_progress(username):
    url = f"https://duome.eu/{username}"
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        
        # Fetch the profile name
        profile_name_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h3 span.json-name"))
        )
        profile_name = profile_name_element.text.strip()

        # Fetch the UTC offset
        utc_offset_text = wait.until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/h4/span"))
        ).text
        offset_match = re.search(r"UTC([+-]?\d+)(?::(\d+))?", utc_offset_text)
        hours = int(offset_match.group(1)) if offset_match else 0
        minutes = int(offset_match.group(2) or 0) if offset_match else 0
        profile_utc_offset = timedelta(hours=hours, minutes=minutes)
        
        # Detect local timezone
        local_tz = get_localzone()

        # Open raw data
        raw_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.q.raw"))
        )
        raw_button.click()
        raw_data_element = wait.until(EC.presence_of_element_located((By.ID, "raw")))
        raw_html = raw_data_element.get_attribute("innerHTML")
        
        # Parse raw data
        soup = BeautifulSoup(raw_html, "html.parser")
        xp_entries = soup.find_all("li")
        data = []
        
        for entry in xp_entries:
            text = entry.get_text(strip=True)
            if "XP" in text:
                parts = text.split("·")
                if len(parts) >= 2:
                    datetime_part = parts[0].strip()
                    xp_part = parts[1].strip()
                    xp_match = re.search(r"(\d+)\s*XP", xp_part)
                    if xp_match:
                        xp = int(xp_match.group(1))
                        datetime_split = datetime_part.split(" ")
                        if len(datetime_split) == 2:
                            date = datetime_split[0]
                            time = datetime_split[1]
                            dt_profile = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
                            dt_utc = dt_profile - profile_utc_offset
                            dt_local = dt_utc.replace(tzinfo=pytz.utc).astimezone(local_tz)
                            data.append({
                                "date": dt_local.strftime("%d-%m-%Y"),
                                "time": dt_local.strftime("%H:%M:%S"),
                                "xp": xp
                            })
        
        # Create a DataFrame
        df = pd.DataFrame(data)
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format="%d-%m-%Y %H:%M:%S")
        df.sort_values('datetime', inplace=True)
        df.reset_index(drop=True, inplace=True)

        # Canvas scraping
        canvas_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#myCanvas"))
        )
        canvas_data_url = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas_element
        )
        canvas_image_data = base64.b64decode(canvas_data_url)
        return profile_name, df, canvas_image_data

    finally:
        driver.quit()

# Plotting function
def plot_progress(df, profile_name):
    row_count = len(df)
    plt.figure(figsize=(12, max(4, row_count // 3)))
    plt.barh(df.index, df['xp'], color='#22FF44', edgecolor='black')
    for index, value in enumerate(df['xp']):
        plt.text(value + 5, index, str(value), va='center', fontsize=9, color='black')
    plt.yticks(df.index, df['date'] + ' ' + df['time'], fontsize=10)
    plt.xlabel("XP Gained", fontsize=14)
    plt.ylabel("Lesson (Date & Time)", fontsize=14)
    plt.title(f"{profile_name}'s Progress Visualization", fontsize=16)
    plt.tight_layout(pad=2.0)
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    return buffer

# Streamlit App
def main():
    st.title("Duolingo Progress Tracker")
    st.markdown("Enter a Duolingo username to fetch and visualize their progress.")
    
    username = st.text_input("Enter Duolingo username:")
    if st.button("Fetch Progress"):
        if username:
            with st.spinner("Fetching data..."):
                try:
                    profile_name, df, canvas_image = scrape_duolingo_progress(username)
                    st.success(f"Data fetched successfully for {profile_name}!")
                    
                    # Display progress data
                    st.subheader("Progress Data")
                    st.dataframe(df)

                    # Download data as CSV
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Progress Data (CSV)",
                        data=csv,
                        file_name=f"{profile_name}_progress.csv",
                        mime="text/csv"
                    )

                    # Display and download plot
                    st.subheader("Progress Visualization")
                    plot_buffer = plot_progress(df, profile_name)
                    st.image(plot_buffer, caption="Progress Visualization", use_column_width=True)
                    st.download_button(
                        label="Download Plot (PNG)",
                        data=plot_buffer,
                        file_name=f"{profile_name}_progress_plot.png",
                        mime="image/png"
                    )

                    # Display and download canvas
                    st.subheader("Progress History Canvas")
                    st.image(canvas_image, caption="Progress History Canvas", use_column_width=True)
                    st.download_button(
                        label="Download Canvas (PNG)",
                        data=canvas_image,
                        file_name=f"{profile_name}_history.png",
                        mime="image/png"
                    )
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.warning("Please enter a username.")

if __name__ == "__main__":
    main()
