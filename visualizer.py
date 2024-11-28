import streamlit as st
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
import base64
import re
import os

def fetch_profile_name(driver, wait, username):
    try:
        refresh_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"span[data-id='{username}']"))
        )
        refresh_button.click()
        WebDriverWait(driver, 10).until(EC.staleness_of(refresh_button))
        profile_name_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h3 span.json-name"))
        )
        return profile_name_element.text.strip()
    except Exception:
        return None

def scrape_duolingo_progress(username):
    url = f"https://duome.eu/{username}"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        profile_name = fetch_profile_name(driver, wait, username)
        if not profile_name:
            return None, None, None

        header_element = wait.until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/h4/span"))
        )
        utc_offset_text = header_element.text
        offset_match = re.search(r"UTC([+-]?\d+)(?::(\d+))?", utc_offset_text)
        hours = int(offset_match.group(1)) if offset_match else 0
        minutes = int(offset_match.group(2) or 0) if offset_match else 0
        profile_utc_offset = timedelta(hours=hours, minutes=minutes)
        local_tz = get_localzone()

        raw_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.q.raw"))
        )
        raw_button.click()
        raw_data_element = wait.until(
            EC.presence_of_element_located((By.ID, "raw"))
        )
        raw_html = raw_data_element.get_attribute("innerHTML")
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
                                "date": dt_local.strftime("%d/%m/%Y"),
                                "time": dt_local.strftime("%H:%M:%S"),
                                "xp": xp
                            })

        df = pd.DataFrame(data)
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format="%d/%m/%Y %H:%M:%S")
        df.sort_values('datetime', inplace=True)
        df.reset_index(drop=True, inplace=True)

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

def main():
    st.title("Duolingo Progress Tracker")
    username = st.text_input("Enter Duolingo Username:")
    if st.button("Fetch Progress"):
        if username:
            with st.spinner("Fetching data..."):
                profile_name, df, canvas_image = scrape_duolingo_progress(username)
                if profile_name and not df.empty:
                    st.success(f"Data fetched for {profile_name}!")
                    csv_filename = f"{profile_name}_progress.csv"
                    df.to_csv(csv_filename, index=False)
                    st.download_button(
                        label="Download Data (CSV)",
                        data=open(csv_filename, "rb").read(),
                        file_name=csv_filename,
                        mime="text/csv",
                    )
                    st.subheader(f"{profile_name}'s XP Progress")
                    row_count = len(df)
                    plt.figure(figsize=(12, max(4, row_count // 3)))
                    plt.barh(df.index, df['xp'], color='#22FF44', edgecolor='black')
                    for index, value in enumerate(df['xp']):
                        plt.text(value + 5, index, str(value), va='center', fontsize=9)
                    plt.yticks(df.index, df['date'] + ' ' + df['time'], fontsize=10)
                    plt.xlabel("XP Gained", fontsize=14)
                    plt.ylabel("Date & Time", fontsize=14)
                    plt.title(f"{profile_name}'s XP Progress", fontsize=16)
                    plt.tight_layout(pad=2.0)
                    plot_filename = f"{profile_name}_progress_plot.png"
                    plt.savefig(plot_filename)
                    st.pyplot(plt.gcf())
                    st.download_button(
                        label="Download Plot (PNG)",
                        data=open(plot_filename, "rb").read(),
                        file_name=plot_filename,
                        mime="image/png",
                    )
                    if canvas_image:
                        st.image(canvas_image, caption="Progress History Canvas")
                        st.download_button(
                            label="Download History Canvas (PNG)",
                            data=canvas_image,
                            file_name=f"{profile_name}_history.png",
                            mime="image/png",
                        )
                else:
                    st.error("Invalid username or no data found.")
        else:
            st.warning("Please enter a username.")

if __name__ == "__main__":
    main()
