# --------------------------------------------------------------------------
# Copyright 2014-2016 Digital Sapphire Development Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# --------------------------------------------------------------------------
from __future__ import print_function, unicode_literals

from abc import ABCMeta, abstractmethod
import logging
import os
import time

from jms_utils.terminal import get_correct_answer
import six

from pyupdater import settings
from pyupdater.utils import remove_dot_files, PluginManager
from pyupdater.utils.exceptions import UploaderError, UploaderPluginError

log = logging.getLogger(__name__)


class Uploader(object):
    """Uploads updates to configured servers.  SSH, SFTP, S3
    Will automatically pick the correct uploader depending on
    what is configured thorough the config object

    Sets up client with config values from obj

        Args:

            obj (instance): config object
    """
    def __init__(self, config=None):
        if config:
            self.init(config)

    def init(self, obj):
        """Sets up client with config values from obj

        Args:

            obj (instance): config object
        """
        data_dir = os.path.join(os.getcwd(), settings.USER_DATA_FOLDER)
        self.deploy_dir = os.path.join(data_dir, 'deploy')
        self.uploader = None
        # Files to be uploaded
        self.files = []
        self.test = False

        # Extension Manager
        self.mgr = PluginManager(obj)

    def get_plugin_names(self):
        return self.mgr.get_plugin_names()

    def set_uploader(self, requested_uploader):
        """Returns an uploader object. 1 of S3, SCP, SFTP.
        SFTP uploaders not supported at this time.

        Args:

            requested_uploader (string): Either s3 or scp

        Returns:

            object (instance): Uploader object
        """
        if isinstance(requested_uploader, six.string_types) is False:
            raise UploaderError('Must pass str to set_uploader',
                                expected=True)

        self.uploader = self.mgr.get_plugin(requested_uploader, init=True)
        if self.uploader is None:
            log.debug('PLUGIN_NAMESPACE: %s', self.mgr.PLUGIN_NAMESPACE)
            raise UploaderPluginError('Requested uploader is not installed',
                                      expected=True)

        msg = 'Requested uploader: {}'.format(requested_uploader)
        log.debug(msg)
        try:
            _files = os.listdir(self.deploy_dir)
        except OSError:
            _files = []

        files = []
        for f in _files:
            files.append(os.path.join(self.deploy_dir, f))

        self.files = remove_dot_files(files)

    def upload(self):
        """Uploads all files in file_list"""
        failed_uploads = []
        self.files_completed = 1
        self.file_count = len(self.files)
        log.info('Plugin: %s', self.uploader.name)
        log.info('Author: %s', self.uploader.author)
        for f in self.files:
            basename = os.path.basename(f)
            msg = '\n\nUploading: {}' .format(basename)
            msg2 = ' - File {} of {}\n'.format(self.files_completed,
                                               self.file_count)
            print(msg + msg2)
            complete = self.uploader.upload_file(f)

            if complete:
                log.debug('%s uploaded successfully', basename)
                os.remove(f)
                self.files_completed += 1
            else:
                log.debug('%s failed to upload.  will retry', basename)
                failed_uploads.append(f)
        if len(failed_uploads) > 0:
            failed_uploads = self._retry_upload(failed_uploads)
        if len(failed_uploads) < 1:
            print("\nUpload Complete")
            time.sleep(3)
            return True
        else:
            print('The following files were not uploaded')
            for i in failed_uploads:
                log.error('%s failed to upload', os.path.basename(i))
                print(i)
            return False

    def _retry_upload(self, failed_uploads):
        # Takes list of failed downloads and tries to re upload them
        retry = failed_uploads[:]
        failed_uploads = []
        failed_count = len(retry)
        count = 1
        for f in retry:
            msg = '\n\nRetyring: {} - File {} of {}\n'.format(f, count,
                                                              failed_count)
            print(msg)
            complete = self.uploader.upload_file(f)
            if complete:
                log.debug('%s uploaded on retry', f)
                count += 1
            else:
                failed_uploads.append(f)

        return failed_uploads


class AbstractBaseUploaderMeta(type):

    def __call__(cls, *args, **kwargs):
        obj = type.__call__(cls, *args, **kwargs)
        obj.check_attributes()
        return obj


@six.add_metaclass(ABCMeta)
class BaseUploader(object):
    __metaclass__ = AbstractBaseUploaderMeta
    name = None
    author = None
    """Base Uploader.  All uploaders should subclass
    this base class
    """
    def check_attributes(self):
        if self.name is None or self.author is None:
            raise NotImplementedError

    def get_answer(self, question, default=None):
        return get_correct_answer(question, default=default)

    @abstractmethod
    def init_config(self, config):
        """Used to initialize plugin with saved config.

        Args:

            config (dict): config dict for plugin
        """
        raise NotImplementedError('Must be implemented in subclass.')

    @abstractmethod
    def set_config(self, config):
        """Used to ask user questions and return config
        for saving

        Args:

            config (dict): config dict that can be used to query
                            already set values

        """
        raise NotImplementedError('Must be implemented in a subclass.')

    @abstractmethod
    def upload_file(self, filename):
        """Uploads file to remote repository

        Args:
            filename (str): file to upload

        Returns:
            (bool) Meaning::

                True - Upload Successful

                False - Upload Failed
        """
        raise NotImplementedError('Must be implemented in subclass.')