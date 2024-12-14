# Required Libraries
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import base64
import time
import re

# Function to scrape Duolingo progress
def scrape_duolingo_progress(username):
    url = f"https://duome.eu/{username}"
    
    # Selenium WebDriver Configuration
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    
    try:
        # Open URL
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        # Step 1: Click the refresh button
        refresh_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/p/b/span")))
        refresh_button.click()
        time.sleep(7)  # Delay to let data refresh

        # Step 2: Scrape profile name
        profile_name_element = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[3]/div[1]/div[3]/h3/span")))
        profile_name = profile_name_element.text.strip()

        # Step 3: Scrape player's timezone
        timezone_element = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/h4/span")))
        timezone = timezone_element.text.strip()

        # Step 4: Click the raw button to open the popup
        raw_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/h4/a")))
        raw_button.click()
        time.sleep(3)  # Delay for popup to load

        # Step 5: Scrape XP data from the popup
        raw_data_element = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='raw']/ul")))
        raw_html = raw_data_element.get_attribute("outerHTML")
        soup = BeautifulSoup(raw_html, "html.parser")
        
        xp_data = []
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
                        # Format date and time (dd/mm/yyyy, 12-hour format)
                        try:
                            parsed_datetime = datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            parsed_datetime = datetime.strptime(datetime_part, "%d-%m-%Y %H:%M:%S")
                        formatted_date = parsed_datetime.strftime("%d/%m/%Y")
                        formatted_time = parsed_datetime.strftime("%I:%M:%S %p")
                        xp_data.append({"date": formatted_date, "time": formatted_time, "xp": xp})
        
        # Sort XP data by datetime in descending order
        xp_data.sort(key=lambda x: datetime.strptime(x["date"] + " " + x["time"], "%d/%m/%Y %I:%M:%S %p"), reverse=True)
        xp_df = pd.DataFrame(xp_data)

        # Step 6: Scrape the progress history canvas as PNG
        canvas_element = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='myCanvas']")))
        canvas_data_url = driver.execute_script("return arguments[0].toDataURL('image/png').substring(22);", canvas_element)
        canvas_image = base64.b64decode(canvas_data_url)

        return profile_name, timezone, xp_df, canvas_image

    except Exception as e:
        return None, None, None, None

    finally:
        driver.quit()

# Streamlit App
def main():
    st.title("Duolingo Progress Tracker")
    st.markdown("Visualize Duolingo users progress with a detailed XP chart and downloadable data.\nN.B.Please click fetch progress a few times if data is too old.")
    
    username = st.text_input("Enter Duolingo username:")
    
    if st.button("Fetch Progress"):
        if username:
            with st.spinner("Fetching progress..."):
                profile_name, timezone, xp_df, canvas_image = scrape_duolingo_progress(username)
                
                # Exit function if the username is invalid or no data is found
                if not profile_name or xp_df.empty:
                    st.error("❌ Wrong username or no data found. Please try again.")
                    return
                
                # Display user profile information
                st.success(f"Data fetched successfully for {profile_name}!")
                st.markdown(f"**Timezone:** {timezone}")

                # Save and display XP data in CSV format
                csv_filename = f"{profile_name.replace(' ', '_')}_progress.csv"
                xp_df.to_csv(csv_filename, index=False)
                st.markdown("### Full XP Data:")
                st.dataframe(xp_df, use_container_width=True)  # Display CSV data in full width

                st.download_button(
                    label="Download XP Data as CSV",
                    data=open(csv_filename, "rb").read(),
                    file_name=csv_filename,
                    mime="text/csv",
                )

                # Visualize XP Data

                st.subheader(f"{profile_name}'s XP Progress")

                

                # Reverse the order of the plot (opposite of CSV)

                xp_df_reversed = xp_df.iloc[::-1]



                fig, ax = plt.subplots(figsize=(12, max(5, len(xp_df_reversed) // 5)))  # Dynamic height

                bars = ax.barh(

                    xp_df_reversed["date"] + " " + xp_df_reversed["time"], 

                    xp_df_reversed["xp"], 

                    color="#78C800", 

                    edgecolor="black",
                )
                # Add XP labels to bars
                for bar in bars:
                    width = bar.get_width()
                    ax.text(
                        width + 5,  # Position slightly to the right of the bar
                        bar.get_y() + bar.get_height() / 2, 
                        f"{int(width)} XP", 
                        va="center", 
                        fontsize=10
                    )
                ax.set_xlabel("XP Gained")
                ax.set_ylabel("Date & Time")
                ax.set_title("XP Progress Over Time")
                plt.tight_layout()

                # Save and Show Chart
                chart_filename = f"{profile_name.replace(' ', '_')}_xp_chart.png"
                plt.savefig(chart_filename)
                st.pyplot(fig)

                st.download_button(
                    label="Download Chart as PNG",
                    data=open(chart_filename, "rb").read(),
                    file_name=chart_filename,
                    mime="image/png",
                )

                # Show and Download Canvas Image
                if canvas_image:
                    st.image(canvas_image, caption="Progress History Canvas", use_container_width=True)
                    st.download_button(
                        label="Download Progress History (PNG)",
                        data=canvas_image,
                        file_name=f"{profile_name.replace(' ', '_')}_history.png",
                        mime="image/png",
                    )
        else:
            st.warning("Please enter a username.")

# Footer
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

# Main Function
if __name__ == "__main__":
    main()
    add_footer()
