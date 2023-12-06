import pandas as pd
from bs4 import BeautifulSoup
import requests

from utils import safe_request, sanitize_mojibake, html_to_markdown, markdown_to_html, sanitize_filename

from get_flashbots_writings import fetch_flashbots_writing_contents_and_save_as_pdf
from src.utils import root_directory
from concurrent.futures import ThreadPoolExecutor
import os
import pdfkit
import logging
import markdown
import yaml


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_file_list(GITHUB_API_URL="https://api.github.com/repos/flashbots/flashbots-writings-website/contents/content"):
    response = requests.get(GITHUB_API_URL)
    if response.status_code == 200:
        return response.json()  # Returns a list of file information
    else:
        logging.info(f"Failed to fetch file list from {GITHUB_API_URL}, response code {response.status_code}")
        return []


def fetch_discourse_content_from_url(url, css_selector="div.post[itemprop='articleBody']"):
    """
    Fetch and neatly parse the content of an article from a URL using the specified CSS selector.
    The content is returned in Markdown format.

    Parameters:
    - url (str): The URL of the article.
    - css_selector (str): The CSS selector to locate the content container in the HTML.

    Returns:
    - str: The neatly parsed content of the article in Markdown format, or None if the content could not be fetched.
    """
    try:
        response = safe_request(url)  # Use the safe_request function to handle potential 429 errors.
        if response is None:
            return None, None, None

        response.encoding = 'utf-8'  # Force UTF-8 encoding
        content = response.text

        soup = BeautifulSoup(content, 'html.parser')
        content_container = soup.select_one(css_selector)

        if not content_container:
            logging.warning(f"No content found for URL {url} with selector {css_selector}")
            return None, None, None

        markdown_content = ''.join(html_to_markdown(element) for element in content_container if element.name is not None)
        markdown_content = sanitize_mojibake(markdown_content)  # Clean up the content after parsing

        # Extracting release date
        meta_tag = soup.find('meta', {'property': 'article:published_time'})
        if meta_tag and 'content' in meta_tag.attrs:
            release_date = meta_tag['content'].split('T')[0]
        else:
            release_date = None

        # Find the 'a' tag within the 'span' with class 'creator'
        a_tag = soup.select_one('.creator a')

        # Extract the 'href' attribute
        authors = a_tag['href'] if a_tag else None

        logging.info(f"Fetched content for URL {url}")
        return markdown_content, release_date, authors
    except Exception as e:
        logging.error(f"Could not fetch content for URL {url}: {e}")
        return None, None, None


def fetch_content(row, output_dir):
    url = getattr(row, 'article')

    # Define a mapping of URL patterns to functions

    url_patterns = {
        'ethresear.ch': fetch_discourse_content_from_url,
        'collective.flashbots.net': fetch_discourse_content_from_url,
        'lido.fi': fetch_discourse_content_from_url,
        'research.anoma': fetch_discourse_content_from_url,
        # 'frontier.tech': fetch_frontier_tech_titles,
        # 'vitalik.ca': fetch_vitalik_ca_titles,
        # 'writings.flashbots': fetch_flashbots_writings_titles,
        # 'medium.com': fetch_medium_titles,
        # 'blog.metrika': fetch_medium_titles,
        # 'mirror.xyz': fetch_mirror_titles,
        # 'iex.io': fetch_iex_titles,
        # 'paradigm.xyz': fetch_paradigm_titles,
        # 'hackmd.io': fetch_hackmd_titles,
        # 'jumpcrypto.com': fetch_jump_titles,
        # 'notion.site': fetch_notion_titles,  # Placeholder for fetch_notion_titles
        # 'notes.ethereum.org': fetch_notion_titles,  # Placeholder for fetch_notion_titles
        # 'succulent-throat-0ce.': fetch_notion_titles,  # Placeholder for fetch_notion_titles
        # 'propellerheads.xyz': fetch_propellerheads_titles,
        # 'a16z': fetch_a16z_titles,
        # 'blog.uniswap': None,  # Placeholder for fetch_uniswap_titles
        # 'osmosis.zone': fetch_osmosis_titles,
        # 'mechanism.org': fetch_mechanism_titles,
    }

    # TODO 2023-09-18: add substack support

    for pattern, fetch_function in url_patterns.items():
        if pattern in url:
            if fetch_function:
                content, release_date, authors = fetch_function(url)
                return content, release_date, authors
            else:
                return None, None, None

    return None, None, None  # Default case if no match is found


def fetch_article_contents_and_save_as_pdf(csv_filepath, output_dir, num_articles=None, overwrite=True):
    """
    Fetch the contents of articles and save each content as a PDF in the specified directory.

    Parameters:
    - csv_filepath (str): The file path of the input CSV file containing article URLs and referrers.
    - output_dir (str): The directory where the article PDFs should be saved.
    - num_articles (int, optional): Number of articles to process. If None, process all articles.
    """
    # Read the CSV file and prepare for updating
    df = pd.read_csv(csv_filepath)
    if 'release_date' not in df.columns:
        df['release_date'] = None

    if 'authors' not in df.columns:
        df['authors'] = None

    # If num_articles is specified, slice the DataFrame
    if num_articles is not None:
        df = df.head(num_articles)

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Function to process each row
    def process_row(row):
        article_url = getattr(row, 'article')
        article_title = getattr(row, 'title')

        import numpy as np
        if article_title is np.nan:
            article_title = article_url

        # Create a sanitized file name for the PDF from the article title
        pdf_filename = os.path.join(output_dir, article_title.replace("/", "<slash>") + '.pdf')

        # Check if PDF already exists
        if not os.path.exists(pdf_filename) or overwrite:
            content, release_date, authors = fetch_content(row, output_dir)
            if content:
                # Specify additional options for pdfkit to ensure UTF-8 encoding
                options = {
                    'encoding': "UTF-8",
                    'custom-header': [
                        ('Content-Encoding', 'utf-8'),
                    ],
                    'no-outline': None
                }
                pdfkit.from_string(markdown_to_html(content), pdf_filename, options=options)
                logging.info(f"Saved PDF for {article_url}")

            else:
                # logging.warning(f"No content fetched for {article_url}")
                pass
                # Update the dataframe with the release date
            if release_date:
                df.loc[df['title'] == getattr(row, 'title'), 'release_date'] = release_date
            if authors:
                df.loc[df['title'] == getattr(row, 'title'), 'authors'] = authors

    # Use ThreadPoolExecutor to process rows in parallel
    with ThreadPoolExecutor() as executor:
        list(executor.map(process_row, df.itertuples()))

    # Save the updated DataFrame
    df.to_csv(csv_filepath, index=False)


def run():
    csv_file_path = f'{root_directory()}/data/links/articles_updated.csv'
    output_directory = f'{root_directory()}/data/articles_pdf_download/'
    fetch_article_contents_and_save_as_pdf(csv_filepath=csv_file_path, output_dir=output_directory, overwrite=True)
    fetch_flashbots_writing_contents_and_save_as_pdf(output_directory)


run()
