# Install necessary libraries if needed
# pip install streamlit selenium pandas matplotlib beautifulsoup4 pytz tzlocal

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
import time

# Define the main scraping function
def scrape_duolingo_progress(username):
    url = f"https://duome.eu/{username}"
    
    # Configure Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    data = []
    canvas_image = None
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        
        # Check if profile exists
        profile_name_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h3 span.json-name"))
        )
        profile_name = profile_name_element.text.strip()
        
        # Click the refresh button to ensure updated data
        refresh_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"span[data-id='{username}']"))
        )
        refresh_button.click()
        
        # Allow data to load after refresh
        time.sleep(5)  # Adjust based on observed delays
        
        # Get raw data
        raw_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.q.raw"))
        )
        raw_button.click()
        
        raw_data_element = wait.until(
            EC.presence_of_element_located((By.ID, "raw"))
        )
        raw_html = raw_data_element.get_attribute("innerHTML")
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Parse raw XP data
        xp_entries = soup.find_all("li")
        local_tz = get_localzone()
        for entry in xp_entries:
            text = entry.get_text(strip=True)
            if "XP" in text:
                parts = text.split("·")
                if len(parts) >= 2:
                    datetime_part = parts[0].strip()
                    xp_match = re.search(r"(\d+)\s*XP", parts[1])
                    if xp_match:
                        xp = int(xp_match.group(1))
                        date, time_part = datetime_part.split(" ")
                        datetime_profile = datetime.strptime(f"{date} {time_part}", "%Y-%m-%d %H:%M:%S")
                        datetime_local = datetime_profile.astimezone(local_tz)
                        data.append({
                            "date": datetime_local.strftime("%d-%m-%Y"),
                            "time": datetime_local.strftime("%H:%M:%S"),
                            "xp": xp
                        })
        
        # Capture canvas image
        canvas_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#myCanvas"))
        )
        canvas_data_url = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(22);", canvas_element
        )
        canvas_image = base64.b64decode(canvas_data_url)
        
        # Return profile name, data, and canvas image
        return profile_name, pd.DataFrame(data), canvas_image
    
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, None
    finally:
        driver.quit()

# Streamlit interface
def main():
    st.title("🦉 Duolingo Progress Tracker")
    st.markdown("Enter a Duolingo username to fetch and visualize their progress!")
    
    username = st.text_input("Enter Duolingo username:")
    
    if st.button("Fetch Progress"):
        if username:
            with st.spinner("Fetching data..."):
                profile_name, df, canvas_image = scrape_duolingo_progress(username)
                if profile_name and not df.empty:
                    st.success(f"Data fetched successfully for {profile_name}!")
                    
                    # Save data to CSV
                    csv_filename = f"{profile_name}_progress.csv"
                    df.to_csv(csv_filename, index=False)
                    st.download_button(
                        label="Download Progress Data (CSV)",
                        data=open(csv_filename, "rb").read(),
                        file_name=csv_filename,
                        mime="text/csv",
                    )
                    
                    # Plot XP data
                    st.subheader(f"{profile_name}'s Progress Visualization")
                    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
                    df.sort_values('datetime', inplace=True)
                    
                    plt.figure(figsize=(10, 6))
                    plt.barh(df['datetime'].dt.strftime('%d-%m %H:%M'), df['xp'], color='#22FF44', edgecolor='black')
                    plt.xlabel("XP Gained")
                    plt.ylabel("Date & Time")
                    plt.title("XP Progress Over Time")
                    
                    # Save the plot
                    plot_filename = f"{profile_name}_progress_plot.png"
                    plt.savefig(plot_filename)
                    st.pyplot(plt.gcf())
                    
                    # Download button for plot
                    st.download_button(
                        label="Download Plot (PNG)",
                        data=open(plot_filename, "rb").read(),
                        file_name=plot_filename,
                        mime="image/png",
                    )
                    
                    # Show and download canvas image
                    if canvas_image:
                        st.image(canvas_image, caption="Progress History Canvas", use_container_width=True)
                        st.download_button(
                            label="Download History Canvas (PNG)",
                            data=canvas_image,
                            file_name=f"{profile_name}_history.png",
                            mime="image/png",
                        )
                else:
                    st.error("❌ No data found or invalid username. Please try again.")
        else:
            st.warning("Please enter a username.")

if __name__ == "__main__":
    main()
