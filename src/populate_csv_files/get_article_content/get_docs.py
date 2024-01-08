import requests
import os
import pdfkit
import logging
import time
from markdown import markdown
from src.utils import root_directory
import dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from weasyprint import HTML


# Load environment variables
dotenv.load_dotenv()
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_content_list(github_api_url, headers, retry_count=3, delay=5):
    try:
        response = requests.get(github_api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403 and 'rate limit exceeded' in e.response.text:
            if retry_count > 0:
                logging.warning(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                return get_content_list(github_api_url, headers, retry_count-1, delay*2)
        logging.error(f"Error fetching content from {github_api_url}: {e}")
        return []

def process_directory(output_dir, api_url, headers, overwrite=True, exclude_dirs=None):
    # Check if the current directory is in the exclude list
    if exclude_dirs and any(ex_dir in output_dir for ex_dir in exclude_dirs):
        logging.info(f"Skipping excluded directory: {output_dir}")
        return

    contents = get_content_list(api_url, headers)
    if not contents:
        logging.error(f"No contents found at API URL: {api_url}")
        return

    logging.info(f"Processing directory: {output_dir}")

    with ThreadPoolExecutor() as executor:
        futures = []

        for content in contents:
            if content['type'] == 'file' and content['name'].endswith(('.md', '.mdx')):
                future = executor.submit(process_file, output_dir, content, headers, overwrite)
                futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error processing a file: {e}")

    # Process subdirectories sequentially
    for content in contents:
        if content['type'] == 'dir':
            new_output_dir = os.path.join(output_dir, content['name'])
            new_api_url = content['url']
            os.makedirs(new_output_dir, exist_ok=True)
            logging.info(f"Processing subdirectory: {content['name']}")
            process_directory(new_output_dir, new_api_url, headers, overwrite, exclude_dirs)

    # logging.info(f"Finished processing directory: {output_dir}")



def process_file(output_dir, file_info, headers, overwrite):
    file_name = file_info['name']
    output_pdf_path = os.path.join(output_dir, file_name.replace('.md', '.pdf').replace('.mdx', '.pdf'))

    if not overwrite and os.path.exists(output_pdf_path):
        # logging.info(f"File already exists: {output_pdf_path}. Skipping download and conversion.")
        return

    try:
        file_url = file_info['download_url']
        file_content = requests.get(file_url, headers=headers).text
        convert_to_pdf_with_fallback(file_content, output_pdf_path)
        logging.info(f"Successfully processed and saved: {output_pdf_path}")
    except Exception as e:
        logging.error(f"Error processing file {file_name}: {e}")


def convert_to_pdf_with_fallback(markdown_content, output_pdf_path, retry_count=3, delay=5):
    # First try using pdfkit
    try:
        html_content = prepare_html_content(markdown_content)
        options = {
            'encoding': "UTF-8",
            'custom-header': [('Content-Encoding', 'utf-8')],
            'no-outline': None
        }
        pdfkit.from_string(html_content, output_pdf_path, options=options)
        return True
    except Exception as e:
        logging.warning(f"pdfkit failed to convert to PDF: {e}. Trying WeasyPrint...")

    # If pdfkit fails, try using WeasyPrint
    try:
        HTML(string=html_content).write_pdf(output_pdf_path)
        return True
    except Exception as e:
        if retry_count > 0:
            logging.warning(f"WeasyPrint also failed to convert to PDF: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
            return convert_to_pdf_with_fallback(markdown_content, output_pdf_path, retry_count-1, delay*2)

    logging.error(f"Failed to convert to PDF after retries: {output_pdf_path}")
    return None


def prepare_html_content(markdown_content):
    # Convert Markdown to HTML
    html_content = '<meta charset="UTF-8">' + markdown(markdown_content, extensions=['md_in_html'])
    # Remove or modify image tags
    html_content = remove_images(html_content)
    return html_content

def remove_images(html_content):
    """
    Removes or modifies image tags in HTML content.

    This function parses the given HTML content and removes all image tags
    (`<img>`). This is a crucial step to avoid errors during PDF conversion
    caused by image tags. These errors can occur due to various reasons such
    as relative image paths not resolving correctly in the context of the PDF
    generator, missing image files, or unsupported URI schemes in the `src`
    attribute of image tags.

    Parameters:
    html_content (str): The HTML content from which images are to be removed.

    Returns:
    str: HTML content with image tags removed or modified.

    Note:
    The function uses BeautifulSoup for parsing and manipulating the HTML
    content. Image tags are completely removed in this implementation, but
    could be replaced with alternative text or placeholders if desired.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    for img in soup.find_all('img'):
        img.decompose()  # This will remove the image tag completely
    return str(soup)


def fetch_and_save_as_pdf(output_dir, repo_api_url, headers, exclude_dirs, overwrite=True):
    # No need to pass executor as an argument here
    process_directory(output_dir, repo_api_url, headers, overwrite, exclude_dirs)

def process_repositories(overwrite=True):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
    exclude_dirs = ['translations']  # List of directories to exclude

    # Flashbots Docs
    # flashbots_output_dir = f'{root_directory()}/data/flashbots_docs_pdf/'
    # flashbots_repo_api_url = "https://api.github.com/repos/flashbots/flashbots-docs/contents/docs"
    # fetch_and_save_as_pdf(flashbots_output_dir, flashbots_repo_api_url, headers, overwrite)

    # Ethereum Org Website
    ethereum_output_dir = f'{root_directory()}/data/ethereum_org_website_content/'
    ethereum_repo_api_url = "https://api.github.com/repos/ethereum/ethereum-org-website/contents/src/content"

    fetch_and_save_as_pdf(ethereum_output_dir, ethereum_repo_api_url, headers, overwrite, exclude_dirs)

if __name__ == "__main__":
    try:
        process_repositories(overwrite=False)
    except Exception as e:
        logging.error(f"Error processing repositories: {e}")