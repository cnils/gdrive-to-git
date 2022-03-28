# local imports
import io
import os

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Google Drive class
class GoogleDrive:
    def __init__(self):
        # delete token.json before changing these
        self.scopes = [
            # 'https://www.googleapis.com/auth/drive.metadata.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        self.creds = None
        self.credentials()
        self.connect()
    
    def credentials(self):
        # store credentials (user access and refresh tokens)
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', self.scopes)
        # if no (valid) credentials available, let user log in
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.scopes)
                self.creds = flow.run_local_server()  # port MUST match redirect URI in Google App
            # save credentials for the next run
            with open('token.json', 'w') as token:
                token.write(self.creds.to_json())
                
    def connect(self):
        # attempt to connect to the API
        try:
            self.service = build('drive', 'v3', credentials=self.creds)
            # self.service = build('gmail', 'v1', credentials=self.creds)  # use later for gmail...
        except HttpError as error:
            print(f'An error occurred: {error}')
            
    def id_get(self, i):
        r = self.service.files().get(fileId=i).execute()
        
        return r
            
    def id_search(self, values, term='name', operator='=', ftype='file', ignore_trashed=True):
        q = f'{term} {operator} "{values}" '
        if ftype == 'folder':
            q += 'and mimeType = "application/vnd.google-apps.folder" '
        elif ftype == 'json':
            q += 'and mimeType = "application/json" '
        if ignore_trashed:
            q += 'and trashed = false'
        l = self.service.files().list(q=q).execute()
        
        return l['files']
            
    def folder_contents(self, i, ignore_trashed=True):
        q = f'"{i}" in parents '
        if ignore_trashed:
            q += 'and trashed = false '
        l = self.service.files().list(q=q).execute()
        
        return l['files']
            
    def get_revisions(self, i):
        try:
            r = self.service.revisions().list(fileId=i).execute()
        
            return r['revisions']
        
        except:
            return
        
    def qry_fields(self, i, r=None, fields=['parents']):
        if r is None:
            p = self.service.files().get(fileId=i, fields=','.join(fields)).execute()
        else:
            p = self.service.revisions().get(fileId=i, revisionId=r, fields=','.join(fields)).execute()
        
        return {f: p[f] for f in fields}
    
    def stream_file(self, i, r=None, out='stream', verbose=False):
        if r is None:
            request = self.service.files().get_media(fileId=i)
        else:
            request = self.service.revisions().get_media(fileId=i, revisionId=r)
        
        if out in ['stream', 'str']:
            stream = io.BytesIO()
        else:
            stream = io.FileIO(out, mode='w')
        downloader = MediaIoBaseDownload(stream, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if verbose:
                print(f'Download {int(status.progress() * 100)}%')
        if verbose:
            print(f'Size {status.total_size / 1024 / 1024:.2f}MB')

        if out in ['str']:
            return stream.getvalue()
        else:
            return stream