# local imports
import os
import time
import pytz
import datetime

# GitPython import
import git

# Google Drive to Git class
class Drive2Git:
    def __init__(self, drive, folder, local_path=os.getcwd(), config={}, ignore_folders=[], ignore_files=[]):
        self.drive = drive
        self.folder = self.check_object(folder)
        self.local_path = local_path
        self.config = self.load_config(config)
        self.ignore_folders = ignore_folders
        self.ignore_files = ignore_files
        self.folder_map = self.map_folder(folder)
        self.name = self.folder_map['path']
    
    def check_object(self, obj):
        # check case: id
        if type(obj) == str:
            print('Getting object info using ID.')
            obj = self.drive.id_get(obj)
        elif type(obj) == list:
            print('Getting object info from first list item.')
            
        return obj
    
    def check_ignore(self, obj, ignorances):
        flag = False
        if obj['name'] in ignorances:
            flag = True
            
        return flag
    
    def load_config(self, config):
        out = {}
        # load UTC
        out['utc'] = pytz.timezone('UTC')
        
        # load author
        if set(['name','email']).issubset(set(config.keys())):
            out['author'] = git.Actor(name=config['name'], email=config['email'])
        else:
            out['author'] = None
            
        # load timezone
        if set(['tz']).issubset(set(config.keys())):
            out['tz'] = pytz.timezone(config['tz'])
        else:
            out['tz'] = out['utc']
            
        return out
        
    def map_folder(self, folder, path=''):
        '''
        Recursive.
        '''
        # check if id used
        folder = self.check_object(folder)
        
        # if root, set path to folder name
        if path == '':
            path = folder['name']

        # scan contents
        contents = []
        for c in self.drive.folder_contents(folder['id']):
            if c['mimeType'] == 'application/vnd.google-apps.folder':
                if not self.check_ignore(c, self.ignore_folders):
                    p = os.path.join(path, c['name'])
                    contents.append(self.map_folder(c, path=p))
            else:
                f = {
                    'path': os.path.join(path, c['name']),
                    'id': c['id'],
                    'name': c['name'],
                    'type': c['mimeType'],
                    'gitignore': self.check_ignore(folder, self.ignore_folders) | self.check_ignore(c, self.ignore_files),
                    'revisions': self.drive.get_revisions(c['id'])
                }
                contents.append(f)
                
        # set up output dictionary
        out = {
            'path': path,
            'id': folder['id'],
            'name': folder['name'],
            'type': folder['mimeType'],
            'gitignore': self.check_ignore(folder, self.ignore_folders),
            'contents': contents
        }
                
        return out
    
    def create_folders(self, folder_map):
        '''
        Recursive.
        '''
        # create "root" folder
        try:
            os.mkdir(os.path.join(self.local_path, folder_map['path']))
        except:
            pass
        
        # map folder
        for c in folder_map['contents']:
            if 'contents' in c.keys():
                self.create_folders(c)
    
    def delete_folders(self, path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
    
    def itemize_revisions(self, folder_map, revisions={}):
        '''
        Recursive.
        '''
        for c in folder_map['contents']:
            if c['type'] == 'application/vnd.google-apps.folder':
                revisions = self.itemize_revisions(c, revisions=revisions)
            else:
                if 'revisions' in c.keys():
                    if len(c['revisions']) >= 100:
                        print(f'Warning: maximum number of Google Drive revisions used or exceeded by {c["name"]}.')
                    for i, r in enumerate(c['revisions']):
                        revision = {
                            'path': c['path'],
                            'id': c['id'],
                            'rid': r['id'],
                            'name': c['name'],
                            'gitignore': c['gitignore'],
                            'version': i + 1
                        }
                        k = r['modifiedTime']
                        v = revisions.get(k, [])
                        if revision['rid'] not in [i['rid'] for i in v]:  # avoids duplicates if rerun
                            v.append(revision)
                            revisions.update({k: v})

        return revisions
    
    def bundle_commits(self, minutes=240):
        # get commits
        commits = self.itemize_revisions(self.folder_map)
        dates = sorted(commits)

        # set time zones
        utc = self.config['utc']
        tz = self.config['tz']

        # initialize variables
        bundle = {}
        rdates = []
        cdates = []
        comms = []

        # loop through sorted dates
        while len(dates) > 0:
            rdate = dates.pop(0)  # oldest -> newest
            parsed_date = datetime.datetime.strptime(rdate, '%Y-%m-%dT%H:%M:%S.%fZ')
            cdate = utc.localize(parsed_date).astimezone(tz)
            com = commits.get(rdate)

            # existing bundle
            if len(cdates) > 0:
                # within bundle threshold
                if (cdate - cdates[-1]).total_seconds() / 60 < minutes:  # time from previous edit
                    # grow bundle
                    rdates.append(rdate)
                    cdates.append(cdate)
                    comms += com  # extend list
                else:
                    # append previous bundle
                    bundle.update({rdates[-1]: {
                        'cdate': cdates[-1],
                        'rdates': rdates,
                        'files': comms
                    }})
                    
                    # start new bundle
                    rdates = [rdate]
                    cdates = [cdate]
                    comms = com
                if len(dates) == 0:
                    # append final bundle
                    bundle.update({rdates[-1]: {
                        'cdate': cdates[-1],
                        'rdates': rdates,
                        'files': comms
                    }})
            else:
                # start new bundle
                rdates = [rdate]
                cdates = [cdate]
                comms = com

        # sort bundle by keys
        self.bundle = dict(sorted(bundle.items()))
    
    def max_versions(self):
        for _, v in self.bundle.items():
            commits = v['files']
            max_versions = {}
            for c in commits:
                i = max_versions.get(c['id'], {})
                if len(i) == 0:
                    max_versions.update({c['id']: c})
                else:
                    if c['version'] > i['version']:
                        max_versions.update({c['id']: c})

            v['files'] = list(max_versions.values())

    def gitignore(self):
        file_path = os.path.join(self.local_path, self.name, '.gitignore')
        
        # remove old .gitignore file
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # add new .gitignore file
        files = self.ignore_folders + self.ignore_files
        with open(file_path, 'w') as f:
            lines = [f'**/{l}\n' for l in files]
            f.writelines(lines)
    
    def make_repo(self, minutes=240, remove='git'):
        # get commit info
        self.bundle_commits(minutes)
        self.max_versions()
        
        # remove any existing git folders
        if remove == 'git':
            remove_path = os.path.join(self.local_path, self.name, '.git')
        elif remove == 'all':
            remove_path = os.path.join(self.local_path, self.name)
        if os.path.isdir(remove_path):
            self.delete_folders(remove_path)
            print('Old git folder removed.\n')

        # configure git repo
        print('Configuring git repo.')
        repo = git.Repo.init(os.path.join(self.local_path, self.name), expand_vars=False)

        # create folders - move up???
        print('Creating folder structure.\n')
        self.create_folders(self.folder_map)

        # auto-commits
        for i, (k, v) in enumerate(self.bundle.items()):
            # make files
            cdate = v['cdate']
            files = v['files']
            print(f'Auto-commit {i+1}, adding {len(files)} updates bundled from {k}...')
            for f in files:
                file_path = os.path.join(self.local_path, f['path'])
                print(f'\t{f["path"]}, v{f["version"]}')
                try:
                    self.drive.stream_file(f['id'], r=f['rid'], out=file_path)
                except:
                    print('\t\tFile error!')

                # add file
                if not f['gitignore']:
                    repo.index.add([file_path])
                else:
                    print(f'\t\tNot added to commit.')
                    
            # add gitignore
            self.gitignore()
            gitignore_path = os.path.join(self.local_path, self.name, '.gitignore')
            repo.index.add([gitignore_path])
            
            # add commit comments
            if i > 0:
                comments = f'Auto-commit {i+1} (via Google Drive-to-git tool).'
            else:
                comments = 'Initial auto-commit (via Google Drive-to-git tool).'
            
            repo.index.commit(comments,
                              author=self.config['author'], committer=self.config['author'],
                              author_date=cdate, commit_date=cdate)
            
        print(f'\nNew git folder written!')