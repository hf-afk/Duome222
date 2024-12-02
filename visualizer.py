# Install necessary libraries if needed
# pip install streamlit selenium pandas matplotlib beautifulsoup4 pytz pillow tzlocal

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
from io import BytesIO
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
    profile_name = None
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        # Click the refresh button
        refresh_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"span[data-id='{username}']"))
        )
        refresh_button.click()
        
        # Wait for the data to refresh and load
        time.sleep(5)  # Adjust delay as needed
        
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

# Plotting function
def plot_progress(df, profile_name):
    # Reverse the DataFrame for ascending order on the Y-axis
    df = df.iloc[::-1].reset_index(drop=True)

    # Plot the horizontal bar chart
    row_count = len(df)
    plt.figure(figsize=(12, max(4, row_count // 3)))
    plt.barh(df.index, df['xp'], color='#22FF44', edgecolor='black')

    # Add XP labels on bars
    for index, value in enumerate(df['xp']):
        plt.text(value + 5, index, str(value), va='center', fontsize=9, color='black')

    # Set Y-axis labels in ascending order of date and time
    plt.yticks(df.index, df['date'] + ' ' + df['time'], fontsize=10)
    plt.xlabel("XP Gained", fontsize=14)
    plt.ylabel("Lesson (Date & Time)", fontsize=14)
    plt.title(f"{profile_name}'s Progress Visualization", fontsize=16)
    plt.tight_layout(pad=2.0)

    # Save the plot to a buffer and return
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    return buffer

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
                    
                    # Display Progress Data
                    st.subheader("Progress Data")
                    st.dataframe(df, use_container_width=True)
                    
                    # Save and Download CSV
                    csv = df[['date', 'time', 'xp']].to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Progress Data (CSV)",
                        data=csv,
                        file_name=f"{profile_name}_progress.csv",
                        mime="text/csv",
                    )
                    
                    # Plot XP data
                    st.subheader(f"{profile_name}'s Progress Visualization")
                    plot_buffer = plot_progress(df, profile_name)
                    st.image(plot_buffer, caption="Progress Visualization", use_column_width=True)
                    st.download_button(
                        label="Download Plot (PNG)",
                        data=plot_buffer,
                        file_name=f"{profile_name}_progress_plot.png",
                        mime="image/png",
                    )
                    
                    # Show and Download Canvas Image
                    if canvas_image:
                        st.subheader("Progress History Canvas")
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

# Footer for branding
def add_footer():
    footer = """
    <style>
        .footer {
            position: fixed;
            bottom: 0;
            right: 0;
            width: 100%;
            text-align: left;
            font-size: 12px;
            padding: 10px;
            color: #777;
        }
    </style>
    <div class="footer">
        © 2024 Made with 💚 by AZIZ.
    </div>
    """
    st.markdown(footer, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    add_footer()
