# Install necessary libraries if needed
# pip install streamlit selenium pandas matplotlib beautifulsoup4 pytz pillow tzlocal webdriver-manager

import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
from tzlocal import get_localzone
import base64
import re
import os

# Define the main scraping function
def scrape_duolingo_progress(username):
    url = f"https://duome.eu/{username}"
    
    # Configure Selenium WebDriver
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(
        service=Service(
            ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
        ),
        options=options,
    )
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
        for entry in xp_entries:
            text = entry.get_text(strip=True)
            if "XP" in text:
                parts = text.split("·")
                if len(parts) >= 2:
                    datetime_part = parts[0].strip()
                    xp_match = re.search(r"(\d+)\s*XP", parts[1])
                    if xp_match:
                        xp = int(xp_match.group(1))
                        date, time = datetime_part.split(" ")
                        data.append({"date": date, "time": time, "xp": xp})
        
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
    st.title("Duolingo Progress Tracker")
    st.markdown("Enter a Duolingo username to fetch and visualize their progress!")
    
    username = st.text_input("Username:")
    
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
                    
                    # Visualization of XP Progress
                    st.subheader(f"{profile_name}'s XP Progress Over Time")
                    
                    # Process the data
                    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%Y-%m-%d %H:%M:%S')
                    df.sort_values('datetime', inplace=True)
                    
                    # Prepare the plot
                    plt.figure(figsize=(12, max(5, len(df) // 3)))  # Dynamic height based on data
                    plt.barh(
                        y=df['datetime'].dt.strftime('%d-%m %H:%M'),  # Format datetime for readability
                        width=df['xp'],
                        color='#22FF44',
                        edgecolor='black'
                    )
                    
                    # Annotate bars with XP values
                    for index, value in enumerate(df['xp']):
                        plt.text(value + 5, index, str(value), va='center', fontsize=10, color='black')
                    
                    # Labels and title
                    plt.xlabel("XP Gained", fontsize=12)
                    plt.ylabel("Date & Time (Sorted)", fontsize=12)
                    plt.title(f"{profile_name}'s XP Progress Visualization", fontsize=14)
                    plt.tight_layout()
                    
                    # Save and display plot
                    plot_filename = f"{profile_name}_progress_plot.png"
                    plt.savefig(plot_filename)
                    st.pyplot(plt.gcf())
                    
                    # Provide download option for the plot
                    st.download_button(
                        label="Download Progress Plot (PNG)",
                        data=open(plot_filename, "rb").read(),
                        file_name=plot_filename,
                        mime="image/png",
                    )

                    
                    # Show and download canvas image
                    if canvas_image:
                        st.image(canvas_image, caption="Progress History Canvas", use_column_width=True)
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
