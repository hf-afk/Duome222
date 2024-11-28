# Install necessary libraries if needed
# pip install streamlit playwright pandas matplotlib beautifulsoup4 pytz pillow tzlocal

import streamlit as st
from playwright.sync_api import sync_playwright
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
    data = []
    canvas_image = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto(url)
            # Check if profile exists
            profile_name = page.locator("h3 span.json-name").inner_text(timeout=5000)
            
            # Click raw data button
            page.locator("a.btn.q.raw").click(timeout=5000)
            
            # Wait for raw data to appear
            page.wait_for_selector("#raw", timeout=5000)
            raw_html = page.locator("#raw").inner_html()
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
            canvas_data_url = page.evaluate(
                "document.querySelector('#myCanvas').toDataURL('image/png').substring(22);"
            )
            canvas_image = base64.b64decode(canvas_data_url)
            
            # Return profile name, data, and canvas image
            return profile_name, pd.DataFrame(data), canvas_image
        
        except Exception as e:
            st.error(f"Error: {e}")
            return None, None, None
        
        finally:
            browser.close()

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
                        st.image(canvas_image, caption="Progress History Canvas", use_column_width=True)
                        st.download_button(
                            label="Download History Canvas (PNG)",
                            data=canvas_image,
                            file_name=f"{profile_name}_history.png",
                            mime="image/png",
                        )
                else:
                    st.error("No data found or invalid username. Please try again.")
        else:
            st.warning("Please enter a username.")

if __name__ == "__main__":
    main()
