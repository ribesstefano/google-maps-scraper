import time
import io

import pandas as pd
import gradio as gr

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("window-size=1280,800")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-features=NetworkService,NetworkServiceInProcess")
chrome_options.add_argument("--enable-features=NetworkServiceOutOfProcess")


def clean_number_string(number_string):
    return number_string.split(" ")[0].replace(".", "").replace(",", ".")

def scrape_data(urls, wait_time, progress):
    progress(0, desc="Starting")
    scraped_data = []

    # Initialize the Chrome driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, wait_time)

    for i, url in enumerate(progress.tqdm(urls, desc="Processing URLs", total=len(urls))):
        driver.get(url)

        # Handle the cookie acceptance dialog
        try:
            if i == 0:
                time.sleep(10)
                reject_field = "Rifiuta tutto"
                cookie_button = driver.find_element(By.XPATH, f"//button[@aria-label='{reject_field}']")
                cookie_button.click()
                gr.Info("Handling of cookie button successful.")
        
        except Exception as e:
            driver.save_screenshot("debug_screenshot_accept_cookies.png")
            html_content = driver.page_source
            with open(f'debug_html_cookies.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            raise gr.Error("Could not find or click the cookie acceptance button. Consider increasing the waiting time per URL.")

        user_data = {}

        user_data['URL'] = url
        user_data['Date'] = time.strftime("%Y/%m/%d")

        try:
            # Extract the name
            name_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.geAzIe.F8kQwb[role='button']")))
            name = name_element.text if name_element else "Name not found"
            user_data['Name'] = name
        except Exception as e:
            print(f"Failed to process {url}: {str(e)}")
            driver.save_screenshot("debug_screenshot.png")
            gr.Warning(f"Unable to extract name for URL: {url}")
            continue

        try:
            # Extract the score
            score_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'span.VEEl9c#ucc-0')))
            user_data['Score'] = clean_number_string(score_element.text)
            score_element.click()
        except Exception as e:
            print(f"Failed to process {url}: {str(e)}")
            driver.save_screenshot("debug_screenshot.png")
            gr.Warning(f"Unable to extract score for URL: {url}")
            continue
        
        try:
            # Allow time for the details to load
            container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.QrGqBf')))
            entries = container.find_elements(By.CSS_SELECTOR, 'div.nKYSz')
        except Exception as e:
            print(f"Failed to process {url}: {str(e)}")
            driver.save_screenshot("debug_screenshot.png")
            gr.Warning(f"Unable to extract fields for URL: {url}")
            continue

        # Extract fields
        fields = {}
        for entry in entries:
            try:
                field_name = entry.find_element(By.CSS_SELECTOR, 'span.FM5HI').text
                field_value = entry.find_element(By.CSS_SELECTOR, 'span.AyEQdd').text
                fields[field_name] = clean_number_string(field_value)
            except Exception as e:
                gr.Warning(f"Error extracting field: {str(e)} for URL: {url}")
        user_data.update(fields)
        
        scraped_data.append(user_data)

    # Close the browser
    driver.quit()

    return scraped_data


def app(file_name, wait_time, progress=gr.Progress()):
    urls = []
    if file_name.endswith('.csv'):
        # Load the content of the CSV directly from the input
        df = pd.read_csv(file_name, encoding="utf-8")
        try:
            urls = df['URL'].unique().tolist()
        except KeyError:
            raise gr.Error("The CSV file must contain a column named 'URL'.")
    else:
        # Read the content directly as text, with one URL per line
        with io.open(file_name, mode='r', encoding="utf-8") as f:
            urls = f.read().splitlines()

    urls = [url.strip().replace('\ufeff', '') for url in urls if url.strip()]
    
    gr.Info(f"Processing {len(urls)} URLs.")

    data = scrape_data(urls, wait_time, progress=progress)
    new_df = pd.DataFrame(data)
    
    if file_name.endswith('.csv'):
        updated_df = pd.concat([df, new_df], ignore_index=True)
    else:
        updated_df = new_df
    
    updated_df.to_csv("updated_data.csv", index=False)
    return "updated_data.csv"

gr.Interface(
    fn=app,
    inputs=[
        gr.components.File(label="Upload CSV or Text File", file_count="single", type="filepath"),
        gr.components.Slider(1, 60, step=1, value=30, label="Max waiting time per URL (seconds)")
    ],
    outputs=gr.components.File(label="Download Updated CSV", type="filepath"),
    title="Google Maps Data Scraper",
    description="Upload a CSV file with URLs or a plain text file with one URL per line. The app will scrape the data and update the CSV file.",
    theme="compact",
    submit_btn="Scrape Data",
    allow_flagging="never",
).launch(debug=True)
