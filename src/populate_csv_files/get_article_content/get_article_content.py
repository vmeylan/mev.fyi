import time
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup
import requests
import pdfkit
import logging
import json
import os
import re
import markdown

from src.populate_csv_files.get_article_content.utils import safe_request, sanitize_mojibake, html_to_markdown, markdown_to_html, convert_date_format, convert_frontier_tech_date_format, convert_mirror_date_format
from src.populate_csv_files.get_article_content.get_flashbots_writings import fetch_flashbots_writing_contents_and_save_as_pdf
from src.utils import root_directory, return_driver
from concurrent.futures import ThreadPoolExecutor

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
            return {
                'content': None,
                'release_date': None,
                'authors': None,
                'author_urls': None,
                'author_firm_name': None,
                'author_firm_url': None
            }

        response.encoding = 'utf-8'  # Force UTF-8 encoding
        content = response.text

        soup = BeautifulSoup(content, 'html.parser')
        content_container = soup.select_one(css_selector)

        if not content_container:
            logging.warning(f"No content found for URL {url} with selector {css_selector}")
            return {
                'content': None,
                'release_date': None,
                'authors': None,
                'author_urls': None,
                'author_firm_name': None,
                'author_firm_url': None
            }

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
        return {
            'content': markdown_content,
            'release_date': release_date,
            'authors': authors,
            'author_urls': None,
            'author_firm_name': None,
            'author_firm_url': None
        }
    except Exception as e:
        logging.error(f"Could not fetch content for URL {url}: {e}")
        return {
            'content': None,
            'release_date': None,
            'authors': None,
            'author_urls': None,
            'author_firm_name': None,
            'author_firm_url': None
        }


def fetch_medium_content_from_url(url):
    try:
        response = requests.get(url)
        response.encoding = 'utf-8'
        content = response.text

        soup = BeautifulSoup(content, 'html.parser')
        # Find the article tag
        article_tag = soup.find('article')
        # Within the article tag, find the section
        section_tag = article_tag.find('section') if article_tag else None

        # Within the section, find the third div which seems to be the container of the content
        content_div = section_tag.find_all('div')[2] if section_tag else None  # Indexing starts at 0; 2 means the third div

        # Initialize a list to hold all markdown content
        content_list = []

        # Loop through all content elements
        for elem in content_div.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
            markdown = html_to_markdown(elem)  # Assuming html_to_markdown is defined
            content_list.append(markdown)

        # Join all the content into a single string with markdown
        markdown_content = '\n'.join(content_list)
        markdown_content = sanitize_mojibake(markdown_content)  # Assuming sanitize_mojibake is defined

        # Extract title
        title_tag = soup.find('title')
        title = title_tag.text if title_tag else None

        # Extract author URL
        author_meta_tag = soup.find('meta', {'property': 'article:author'})
        author_url = author_meta_tag['content'] if author_meta_tag else None

        author_name_tag = soup.find('meta', {'name': 'author'})
        author_name = author_name_tag['content'] if author_name_tag else None

        # Extract publish date using 'data-testid' attribute
        publish_date_tag = soup.find(attrs={"data-testid": "storyPublishDate"})
        publish_date = publish_date_tag.text.strip() if publish_date_tag else None
        publish_date = convert_date_format(publish_date)

        # Extract firm name and URL from script tag
        script_tag = soup.find('script', type='application/ld+json')
        if script_tag:
            data = json.loads(script_tag.string)
            author_firm_name = data.get("publisher", {}).get("name")
            author_firm_url = data.get("publisher", {}).get("url")
        else:
            author_firm_name = None
            author_firm_url = None

        return {
            'content': markdown_content,
            'release_date': publish_date,
            'authors': author_name,
            'author_urls': author_url,
            'author_firm_name': author_firm_name,
            'author_firm_url': author_firm_url
        }
    except Exception as e:
        print(f"Error fetching content from URL {url}: {e}")
        return {
            'content': None,
            'release_date': None,
            'authors': None,
            'author_urls': None,
            'author_firm_name': None,
            'author_firm_url': None
        }


def fetch_mirror_content_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
        content = response.text

        soup = BeautifulSoup(content, 'html.parser')

        # Extract title
        title_tag = soup.find('title')
        title = title_tag.text if title_tag else 'N/A'

        # Extract publish date
        publish_date_tag = soup.find('span', string=re.compile(r'\b(?:\d{1,2}(?:st|nd|rd|th), \d{4})\b'))
        publish_date = publish_date_tag.text.strip() if publish_date_tag else 'N/A'
        publish_date = convert_mirror_date_format(publish_date)  # Assuming convert_mirror_date_format is defined

        # Extract author URL
        author_a_tag = soup.find('a', {'data-state': 'closed'})

        # Extract the URL
        author_url = author_a_tag['href'] if author_a_tag and author_a_tag.has_attr('href') else None

        # Extract author name
        # Find the div that contains the author name 'Rated'
        author_name_div = soup.find('div', class_='_2gklefg')
        author_name = author_name_div.text if author_name_div else 'N/A'

        # Initialize a list to hold all markdown content
        content_list = []

        # Find the container for the content
        content_container = soup.select_one('.css-72ne1l > div:nth-child(1)')
        if content_container is not None:
            # Loop through all content elements within the container
            for elem in content_container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'div']):
                markdown = html_to_markdown(elem)  # Assuming html_to_markdown is defined
                content_list.append(markdown)

        # Join all the content into a single string with markdown
        markdown_content = '\n'.join(content_list)
        markdown_content = sanitize_mojibake(markdown_content)  # Assuming sanitize_mojibake is defined

        return {
            'title': title,
            'content': markdown_content,
            'release_date': publish_date,
            'authors': author_name,
            'author_urls': author_url,
            'author_firm_name': None,  # No information provided for this
            'author_firm_url': None  # No information provided for this
        }
    except Exception as e:
        print(f"Error fetching content from URL {url}: {e}")
        return {
            'title': 'N/A',
            'content': None,
            'release_date': None,
            'authors': None,
            'author_urls': None,
            'author_firm_name': None,
            'author_firm_url': None
        }


def fetch_frontier_tech_content_from_url(url):
    try:
        response = requests.get(url)
        response.encoding = 'utf-8'
        content = response.text

        soup = BeautifulSoup(content, 'html.parser')

        # Extract title
        title_tag = soup.find('h1', class_='notion-header__title')
        title = title_tag.text.strip() if title_tag else None

        # Extract author
        author_tag = soup.find('div', class_='notion-callout__content')
        author = author_tag.text.strip() if author_tag else None

        # Extract date
        date_tag = soup.find('div', class_='notion-callout__content', string=re.compile(r'\d{1,2} \w+ \d{4}'))
        date = date_tag.text.strip() if date_tag else None
        date = convert_frontier_tech_date_format(date)

        # Extract content
        content_list = []
        for content_tag in soup.select('.notion-text, .notion-heading, .notion-bulleted-list'):
            markdown = html_to_markdown(content_tag)
            content_list.append(markdown)
        content_markdown = ''.join(content_list)

        return {
            'title': title,
            'authors': author,
            'release_date': date,
            'content': content_markdown
        }
    except Exception as e:
        print(f"Error fetching content from URL {url}: {e}")
        return None


def extract_notion_content(page_source):
    soup = BeautifulSoup(page_source, 'html.parser')
    content_list = []

    # This function will extract text and links recursively and maintain structure
    def extract_content(html_element):
        for child in html_element.children:
            if child.name == 'a':
                href = child.get('href', '')
                text = child.get_text(strip=True)
                if href:
                    content_list.append(f'[{text}]({href})')
            elif child.name in {'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br'} and not isinstance(child, str):
                # Add a newline before the block-level element if the last addition wasn't a newline
                if content_list and content_list[-1] != '\n':
                    content_list.append('\n')
                extract_content(child)
                # Add a newline after the block-level element
                if child.name != 'div':
                    content_list.append('\n')
            elif child.name is None and isinstance(child, str):  # This is a NavigableString
                stripped_text = child.strip()
                if stripped_text:
                    # Append text to content list, maintaining inline structure
                    content_list.append(stripped_text + ' ')
            else:
                # If it's none of the above, recurse into the child
                extract_content(child)

    # Find the main content container
    content_div = soup.find('div', class_='notion-page-content')
    if content_div:
        extract_content(content_div)

    # Correctly join the content list while respecting the structure
    structured_content = ''.join(content_list).strip()
    # Replace multiple newlines with a single newline
    structured_content = '\n\n'.join(filter(None, structured_content.split('\n')))

    return structured_content


def extract_author_details(url):
    """
    Extracts the author name and author URL from a given URL.

    :param url: The URL to extract details from.
    :return: A dictionary with author name and author URL.
    """
    parsed_url = urlparse(url)
    subdomain = parsed_url.netloc.split('.')[0]  # Assuming the author name is the subdomain
    domain = parsed_url.netloc

    if subdomain == 'www':
        # If the subdomain is www, we assume the second part is the author name
        author_name = parsed_url.netloc.split('.')[1]
    else:
        author_name = subdomain

    author_url = f"{parsed_url.scheme}://{domain}"

    return {
        'authors': author_name,
        'author_urls': author_url
    }

def fetch_notion_content_from_url(url):
    try:
        driver = return_driver()

        try:
            driver.get(url)

            # Wait for some time to allow JavaScript to load content
            driver.implicitly_wait(10)  # Adjust the wait time as necessary
            time.sleep(5)
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Get the page title
            title = driver.title

            date_pattern = re.compile(r'\d{4}/\d{2}/\d{2}')
            # Find the release date using the date pattern
            date_match = date_pattern.search(soup.get_text())
            publish_date = date_match.group(0) if date_match else 'N/A'

            page_source = driver.page_source  # The page source obtained from Selenium
            content = extract_notion_content(page_source)

            author_details = extract_author_details(url)
            print(f"Fetched title [{title}] for URL {url}")

            return {
                'title': title,
                'content': content,
                'release_date': publish_date,
                'authors': author_details['authors'],  # get author name which is the URL subdomain
                'author_urls': author_details['author_urls'],  # get the whole URL domain
                'author_firm_name': None,  # No information provided for this
                'author_firm_url': None  # No information provided for this
            }
        except Exception as e:
            print(f"Error fetching content from URL {url}: {e}")
            return {
                'title': 'N/A',
                'content': None,
                'release_date': None,
                'authors': None,
                'author_urls': None,
                'author_firm_name': None,
                'author_firm_url': None
            }
    finally:
        # Always close the browser to clean up
        driver.quit()


def fetch_content(row, output_dir):
    url = getattr(row, 'article')

    # Define a mapping of URL patterns to functions

    url_patterns = {
        'ethresear.ch': fetch_discourse_content_from_url,
        'collective.flashbots.net': fetch_discourse_content_from_url,
        'lido.fi': fetch_discourse_content_from_url,
        'research.anoma': fetch_discourse_content_from_url,
        'frontier.tech': fetch_frontier_tech_content_from_url,
        # 'vitalik.ca': fetch_vitalik_ca_titles,
        'medium.com': fetch_medium_content_from_url,
        # 'blog.metrika': fetch_medium_titles,
        'mirror.xyz': fetch_mirror_content_from_url,
        # 'iex.io': fetch_iex_titles,
        # 'paradigm.xyz': fetch_paradigm_titles,
        # 'hackmd.io': fetch_hackmd_titles,
        # 'jumpcrypto.com': fetch_jump_titles,
        'notion.site': fetch_notion_content_from_url,  # Placeholder for fetch_notion_titles
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
                content_info = fetch_function(url)
                return content_info

    # Default case if no match is found
    return {
        'content': None,
        'release_date': None,
        'authors': None,
        'author_urls': None,
        'author_firm_name': None,
        'author_firm_url': None
    }


def update_csv(full_df, df, modified_indices, csv_filepath):
    """
    Update specific rows in the full DataFrame based on the modified subset DataFrame and save it to a CSV file.

    :param full_df: The original full DataFrame.
    :param df: The modified subset DataFrame.
    :param modified_indices: A list of indices in df corresponding to the rows modified.
    :param csv_filepath: File path of the CSV file to be updated.
    """
    for idx in modified_indices:
        # Identify the article URL in the modified subset DataFrame
        article_url = df.iloc[idx]['article']

        # Find the corresponding row in the full DataFrame based on article URL
        full_row_index = full_df[full_df['article'] == article_url].index

        # Update the corresponding row in full_df with the modified row in df
        if not full_row_index.empty:
            full_df.loc[full_row_index[0]] = df.iloc[idx]

    # Write the updated full DataFrame to CSV
    full_df.to_csv(csv_filepath, index=False)


def fetch_article_contents_and_save_as_pdf(csv_filepath, output_dir, num_articles=None, overwrite=True, url_filters=None, thread_count=None):
    """
    Fetch the contents of articles and save each content as a PDF in the specified directory.

    Parameters:
    - csv_filepath (str): The file path of the input CSV file containing article URLs and referrers.
    - output_dir (str): The directory where the article PDFs should be saved.
    - num_articles (int, optional): Number of articles to process. If None, process all articles.
    """
    # Read the entire CSV file into a DataFrame
    full_df = pd.read_csv(csv_filepath)
    if 'release_date' not in full_df.columns:
        full_df['release_date'] = None
    if 'authors' not in full_df.columns:
        full_df['authors'] = None

    # Create a filtered subset for processing
    df = full_df.copy()
    if url_filters is not None:
        df = df[df['article'].str.contains('|'.join(url_filters))]
    if num_articles is not None:
        df = df.head(num_articles)

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # List to store indices of modified rows
    modified_indices = []

    # Function to process each row
    def process_row(row, index):
        nonlocal modified_indices
        article_url = getattr(row, 'article')
        article_title = getattr(row, 'title')

        import numpy as np
        if article_title is np.nan:
            article_title = article_url

        # Create a sanitized file name for the PDF from the article title
        pdf_filename = os.path.join(output_dir, article_title.replace("/", "<slash>") + '.pdf')

        # Check if PDF already exists
        if not os.path.exists(pdf_filename) or overwrite:
            content_info = fetch_content(row, output_dir)
            if content_info['content']:
                # Specify additional options for pdfkit to ensure UTF-8 encoding
                options = {
                    'encoding': "UTF-8",
                    'custom-header': [
                        ('Content-Encoding', 'utf-8'),
                    ],
                    'no-outline': None
                }
                if article_title == article_url:
                    # Create a sanitized file name for the PDF from the article title
                    if content_info['title']:
                        article_title = content_info['title']
                        df.loc[df['article'] == getattr(row, 'article'), 'title'] = article_title
                        pdf_filename = os.path.join(output_dir, article_title.replace("/", "<slash>") + '.pdf')

                pdfkit.from_string(markdown_to_html(content_info['content']), pdf_filename, options=options)
                logging.info(f"Saved PDF {article_title} for {article_url}")

            else:
                # logging.warning(f"No content fetched for {article_url}")
                pass
                # Update the dataframe with the release date
            if content_info['release_date']:
                df.loc[df['title'] == getattr(row, 'title'), 'release_date'] = content_info['release_date']
            if content_info['authors']:
                df.loc[df['title'] == getattr(row, 'title'), 'authors'] = content_info['authors']

        # Update the modified rows list
        modified_indices.append(index)

    # Use ThreadPoolExecutor to process rows in parallel
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        executor.map(lambda pair: process_row(pair[1], pair[0]), enumerate(df.itertuples()))

    # Update only the modified rows in the full DataFrame
    update_csv(full_df, df, modified_indices, csv_filepath)


def run(url_filters=None, get_flashbots_writings=True, thread_count=None):
    csv_file_path = f'{root_directory()}/data/links/articles_updated.csv'
    output_directory = f'{root_directory()}/data/articles_pdf_download/'
    fetch_article_contents_and_save_as_pdf(csv_filepath=csv_file_path,
                                           output_dir=output_directory,
                                           overwrite=True,
                                           url_filters=url_filters,
                                           thread_count=thread_count)
    if get_flashbots_writings:
        fetch_flashbots_writing_contents_and_save_as_pdf(output_directory)


if __name__ == "__main__":
    url_filters = ['notion']
    get_flashbots_writings = False
    thread_count = 1
    run(url_filters=url_filters, get_flashbots_writings=get_flashbots_writings, thread_count=thread_count)
