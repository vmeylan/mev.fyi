import os
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import logging

from src.utils import root_directory

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GoogleSheetUpdater:
    def __init__(self, sheet_id, credentials_json):
        self.sheet_id = sheet_id
        self.credentials = Credentials.from_service_account_file(credentials_json, scopes=[
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
        ])
        self.client = gspread.authorize(self.credentials)

    def create_or_get_worksheet(self, tab_name, num_rows, num_cols):
        try:
            sheet = self.client.open_by_key(self.sheet_id).worksheet(tab_name)
            logging.info(f"Worksheet '{tab_name}' already exists.")
        except gspread.WorksheetNotFound:
            sheet = self.client.open_by_key(self.sheet_id).add_worksheet(
                title=tab_name,
                rows=num_rows,
                cols=num_cols
            )
            logging.info(f"Created new worksheet: '{tab_name}'.")
        return sheet

    def update_google_sheet(self, data, tab_name, num_rows, num_cols):
        sheet = self.create_or_get_worksheet(tab_name, num_rows, num_cols)
        df = pd.DataFrame(data)
        set_with_dataframe(sheet, df, row=1, col=1, include_index=False, resize=True)

        service = build('sheets', 'v4', credentials=self.credentials)

        grid_range = {
            'sheetId': sheet.id,
            'startRowIndex': 0,
            'endRowIndex': df.shape[0] + 1,
            'startColumnIndex': 0,
            'endColumnIndex': df.shape[1]
        }

        body = {
            'requests': [{
                'setBasicFilter': {
                    'filter': {
                        'range': grid_range
                    }
                }
            }]
        }

        service.spreadsheets().batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()

        num_columns = df.shape[1]
        resize_requests = []

        for col in range(num_columns):
            resize_requests.append({
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": col,
                        "endIndex": col + 1
                    }
                }
            })

        body = {
            'requests': resize_requests
        }

        service.spreadsheets().batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()
        logging.info(f"Saved data to new tab '{tab_name}' in Google Sheet and added filters.")


if __name__ == "__main__":
    repo_dir = root_directory()
    updater = GoogleSheetUpdater(sheet_id=os.getenv("GOOGLE_SHEET_ID"), credentials_json=os.getenv("GOOGLE_SHEET_CREDENTIALS_JSON"))

    # Update Google Sheet with websites
    websites_txt_file = os.path.join(repo_dir, "data/links/websites.txt")
    websites_data = {'Websites': open(websites_txt_file, 'r').readlines()}
    updater.update_google_sheet(data=websites_data, tab_name="Website Links", num_rows=1000, num_cols=1)

    # Update Google Sheet with YouTube handles
    youtube_txt_file = os.path.join(repo_dir, "data/links/youtube_channel_handles.txt")
    youtube_data = {
        'YouTube Channel Handle': open(youtube_txt_file, 'r').read().split(','),
        'Link': ['https://www.youtube.com/' + handle.strip() for handle in open(youtube_txt_file, 'r').read().split(',')]
    }
    updater.update_google_sheet(data=youtube_data, tab_name="Podcasts and Youtube videos", num_rows=1000, num_cols=2)

    # Update Google Sheet with articles
    articles_csv_file = os.path.join(repo_dir, "data/links/articles.csv")
    articles_data = pd.read_csv(articles_csv_file)
    updater.update_google_sheet(data=articles_data, tab_name="Articles", num_rows=1000, num_cols=2)

    # Update Google Sheet with Twitter threads
    twitter_threads_csv_file = os.path.join(repo_dir, "data/links/twitter_threads.csv")
    twitter_threads_data = pd.read_csv(twitter_threads_csv_file)
    updater.update_google_sheet(data=twitter_threads_data, tab_name="Twitter Threads", num_rows=1000, num_cols=2)