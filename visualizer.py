# Import necessary libraries
import streamlit as st
import pandas as pd
import plotly.express as px
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
        timezone_str = f"UTC{'+' if hours >= 0 else ''}{hours}:{str(minutes).zfill(2)}"
        
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
                                "datetime": dt_local,
                                "xp": xp
                            })

        # Fetch canvas image
        canvas_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#myCanvas"))
        )
        canvas_data_url = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(21);", canvas_element
        )
        canvas_image_data = base64.b64decode(canvas_data_url)

        return profile_name, pd.DataFrame(data), timezone_str, canvas_image_data

    finally:
        driver.quit()

# Streamlit App
def main():
    st.title("🦉 Duolingo Progress Tracker")
    st.markdown("Enter a Duolingo username to fetch and visualize their progress.")
    
    username = st.text_input("Enter Duolingo username:")
    if st.button("Fetch Progress"):
        if username:
            with st.spinner("Fetching data..."):
                try:
                    profile_name, df, timezone_str, canvas_image_data = scrape_duolingo_progress(username)
                    st.success(f"Data fetched successfully for {profile_name}!")
                    
                    # Display player's timezone
                    st.markdown(f"**Player's Timezone:** {timezone_str}")
                    
                    # Display progress data
                    st.subheader("Progress Data")
                    df['datetime_str'] = df['datetime'].dt.strftime('%d-%m-%Y %H:%M:%S')
                    st.dataframe(df[['datetime_str', 'xp']].rename(columns={'datetime_str': 'Date & Time'}), use_container_width=True)

                    # Download data as CSV
                    csv = df[['datetime_str', 'xp']].rename(columns={'datetime_str': 'Date & Time'}).to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Progress Data (CSV)",
                        data=csv,
                        file_name=f"{profile_name}_progress.csv",
                        mime="text/csv"
                    )

                    # Display Plotly visualization
                    st.subheader("Progress Visualization")
                    fig = px.bar(
                        df,
                        x='xp',
                        y='datetime',
                        orientation='h',
                        labels={'xp': 'XP Gained', 'datetime': 'Date & Time'},
                        title=f"{profile_name}'s XP Progress",
                    )
                    fig.update_layout(
                        yaxis=dict(categoryorder='total ascending'),
                        height=max(400, len(df) * 30),  # Dynamically adjust height
                        margin=dict(l=120, r=20, t=40, b=40),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Download Plotly graph as PNG
                    buffer = BytesIO()
                    fig.write_image(buffer, format='png')
                    buffer.seek(0)
                    st.download_button(
                        label="Download Progress Plot (PNG)",
                        data=buffer,
                        file_name=f"{profile_name}_progress_plot.png",
                        mime="image/png"
                    )

                    # Display and download canvas image
                    st.subheader("History Canvas Image")
                    st.image(canvas_image_data, caption="History Canvas", use_column_width=True)
                    st.download_button(
                        label="Download History Canvas (PNG)",
                        data=canvas_image_data,
                        file_name=f"{profile_name}_history.png",
                        mime="image/png"
                    )

                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            st.warning("Please enter a username.")

def add_footer():
    footer = """
    <style>
        /* Position the footer */
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
