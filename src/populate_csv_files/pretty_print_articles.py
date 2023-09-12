import time
import random

import pandas as pd
from bs4 import BeautifulSoup
import requests
from src.utils import root_directory
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver


def fetch_title_from_url(url, css_selector):
    """
    Fetch the title of an article from a URL using the specified CSS selector to locate the title in the HTML.

    Parameters:
    - url (str): The URL of the article.
    - css_selector (str): The CSS selector to locate the title in the HTML.

    Returns:
    - str: The title of the article, or None if the title could not be fetched.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.select_one(css_selector).text.strip()
        print(f"Fetched title [{title}] for URL {url}")
        return title
    except Exception as e:
        print(f"Could not fetch title for URL {url}: {e}")
        return None


def fetch_discourse_titles(url):
    return fetch_title_from_url(url, 'title')


def fetch_frontier_tech_titles(url):
    return fetch_title_from_url(url, 'head > title:nth-child(4)')


def fetch_flashbots_writings_titles(url):
    return fetch_title_from_url(url, '.blogPostTitle_RC3s')


def fetch_mirror_titles(url):
    return fetch_title_from_url(url, 'head > title:nth-child(7)')


def fetch_iex_titles(url):
    return fetch_title_from_url(url, '.header-content-title')


def fetch_paradigm_titles(url):
    return fetch_title_from_url(url, '.Post_post__J7vh4 > h1:nth-child(1)')


def fetch_jump_titles(url):
    return fetch_title_from_url(url, 'h1.MuiTypography-root')


def fetch_propellerheads_titles(url):
    return fetch_title_from_url(url, '.article-title_heading')


def fetch_a16z_titles(url):
    return fetch_title_from_url(url, '.highlight-display > h2:nth-child(1)')


def fetch_uniswap_titles(url):
    return fetch_title_from_url(url, '.p.Type__Title-sc-ga2v53-2:nth-child(1)')


def fetch_notion_titles(url):
    """
    Fetch the title of a notion.site page using Selenium to handle dynamic JavaScript content.

    Parameters:
    - url (str): The URL of the notion.site page.

    Returns:
    - str: The title of the page, or None if the title could not be fetched.
    """
    # set up Chrome driver options
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    CHROME_BINARY_PATH = './env/chrome-linux64/chrome'
    CHROMEDRIVER_PATH = './env/chromedriver-linux64/chromedriver'

    options.binary_location = CHROME_BINARY_PATH

    # Initialize service with the path to your ChromeDriver
    service = webdriver.chrome.service.Service(executable_path=CHROMEDRIVER_PATH)

    browser = webdriver.Chrome(options=options, service=service)

    try:
        browser.get(url)

        # Wait for some time to allow JavaScript to load content
        browser.implicitly_wait(10)  # Adjust the wait time as necessary

        # Get the page title
        title = browser.title
        print(f"Fetched title [{title}] for URL {url}")
        return title
    except Exception as e:
        print(f"Could not fetch title for URL {url}: {e}")
        return None
    finally:
        # Always close the browser to clean up
        browser.quit()


def fetch_hackmd_titles(url):
    """
    Fetch the title of an article from a HackMD URL.

    Parameters:
    - url (str): The URL of the article.

    Returns:
    - str: The title of the article, or None if the title could not be fetched.
    """
    title = None
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title_element = soup.find('title')
        if title_element:
            title = title_element.get_text()
            print(f"Fetched title [{title}] for URL {url}")
        else:
            print(f"Title not found for URL {url}")
    except Exception as e:
        print(f"Could not fetch title for URL {url}: {e}")
        return None
    return title


def fetch_medium_titles(url):
    title = None
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title_element = soup.find('title', {'data-rh': "true"})
        if title_element:
            title = title_element.get_text()
            print(f"The title is: [{title}]")
        else:
            print(f"Title not found for URL {url}")
    except Exception as e:
        print(f"Could not fetch title for URL {url}: {e}")
        return None
    return title


def fetch_vitalik_ca_titles(url):
    title = None
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title_element = soup.find('link', {'rel': 'alternate', 'type': 'application/rss+xml'})
        if title_element and 'title' in title_element.attrs:
            title = title_element['title'].strip()
            print(f"Fetched title [{title}] for URL {url}")
    except Exception as e:
        print(f"Could not fetch title for URL {url} using the rel='alternate' method: {e}")
    return title


def fetch_title(row, url_to_title):
    url = getattr(row, 'article')

    # Check if the title already exists in the output file
    if url in url_to_title and (url_to_title[url] is not None) and not pd.isna(url_to_title[url]):
        return url_to_title[url]

    # do a random sleep from 1 to 3 seconds
    time.sleep(random.randint(1, 3))

    if 'ethresear.ch' in url or 'collective.flashbots.net' in url or 'lido.fi' in url:
        return fetch_discourse_titles(url)
    elif 'frontier.tech' in url:
        return fetch_frontier_tech_titles(url)
    elif 'vitalik.ca' in url:
        return fetch_vitalik_ca_titles(url)
    elif 'writings.flashbots' in url:
        return fetch_flashbots_writings_titles(url)
    elif 'medium.com' in url or 'blog.metrika' in url:
        return fetch_medium_titles(url)
    elif 'mirror.xyz' in url:
        return fetch_mirror_titles(url)
    elif 'iex.io' in url:
        return fetch_iex_titles(url)
    elif 'paradigm.xyz' in url:
        return fetch_paradigm_titles(url)
    elif 'hackmd.io' in url:
        return fetch_hackmd_titles(url)
    elif 'jumpcrypto.com' in url:
        return fetch_jump_titles(url)
    elif 'notion.site' in url or 'notes.ethereum.org' in url or 'succulent-throat-0ce.' in url:
        return None  # fetch_notion_titles(url)
    elif 'propellerheads.xyz' in url:
        return fetch_propellerheads_titles(url)
    elif 'a16z' in url:
        return fetch_a16z_titles(url)
    elif 'blog.uniswap' in url:
        return None  # fetch_uniswap_titles(url)
    else:
        return None


def fetch_article_titles(csv_filepath, output_filepath):
    """
    Fetch the titles of articles from ethresear.ch present in the input CSV file and save them in a new CSV file.

    Parameters:
    - csv_filepath (str): The file path of the input CSV file containing article URLs and referrers.
                          The CSV file should have two columns with headers 'article' and 'referrer'.
    - output_filepath (str): The file path where the output CSV file with the fetched titles should be saved.

    Returns:
    - None
    """
    # Step 1: Read the CSV file with specified column names
    df = pd.read_csv(csv_filepath)

    # Step 1.5: Try to read the existing output file to get already fetched titles
    try:
        output_df = pd.read_csv(output_filepath)
    except FileNotFoundError:
        output_df = pd.DataFrame(columns=['title', 'article', 'referrer'])

    url_to_title = dict(zip(output_df['article'], output_df['title']))

    # Step 2: Loop through the rows and fetch titles for specified URLs
    titles = []

    # Use ThreadPoolExecutor to fetch titles in parallel
    with ThreadPoolExecutor() as executor:
        titles = list(executor.map(fetch_title, df.itertuples(), [url_to_title]*len(df)))

    # Step 3: Save titles in a new column
    df['title'] = titles

    # Step 4: Save the updated DataFrame to a new CSV file
    df = df[['title', 'article', 'referrer']]
    df.to_csv(output_filepath, index=False)


# Usage example:
fetch_article_titles(f'{root_directory()}/data/links/articles.csv', f'{root_directory()}/data/links/articles_updated.csv')