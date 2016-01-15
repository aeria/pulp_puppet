import json
import unittest
import base64
import urlparse

import mock
from pulp_puppet.forge.views.files import FilesView, FilesPost36View


class TestFilesView(unittest.TestCase):
    """
    Tests for FilesView.
    """
    FAKE_VIEW_DATA = {'foo/bar': [{'version': '1.0.0', 'file': '/tmp/foo', 'dependencies': []}]}

    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_credentials')
    def test_files_missing_module(self, mock_get_credentials, mock_get_module_name):
        """
        Test that proper response is returned when module name is not specified
        """
        mock_get_module_name.return_value = ''
        mock_get_credentials.return_value = ()
        mock_request = mock.MagicMock()

        files_view = FilesView()
        response = files_view.get(mock_request, resource_type='repository', resource='repo-id')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'Module name is missing.')

    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_credentials')
    def test_files_missing_auth(self, mock_get_credentials, mock_get_module_name):
        """
        Test that 401 is returned when basic auth is not used for pre 3.3
        """
        mock_get_module_name.return_value = 'fake-module'
        mock_get_credentials.return_value = ()
        mock_request = mock.MagicMock()

        files_view = FilesView()
        response = files_view.get(mock_request)
        self.assertEqual(response.status_code, 401)

    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_credentials')
    def test_files_bad_resource_type(self, mock_get_credentials, mock_get_module_name):
        """
        Test that only consumer or repository resource type is allowed
        """
        mock_get_module_name.return_value = 'fake-module'
        mock_get_credentials.return_value = ()
        mock_request = mock.MagicMock()

        files_view = FilesView()
        response = files_view.get(mock_request, resource_type='foo')
        self.assertEqual(response.status_code, 404)

    def test_files_get_credentials(self):
        """
        Test getting credentials from header
        """
        files_view = FilesView()
        real_creds = ('test', '123')
        encoded_creds = base64.encodestring('test:123')
        headers = {'HTTP_AUTHORIZATION': encoded_creds}
        creds = files_view._get_credentials(headers)
        self.assertEqual(real_creds, creds)

    def test_files_get_bad_credentials(self):
        """
        Test getting improperly formatted credentials from header
        """
        files_view = FilesView()
        encoded_creds = base64.encodestring('blah')
        headers = {'HTTP_AUTHORIZATION': encoded_creds}
        creds = files_view._get_credentials(headers)
        self.assertEqual(creds, None)

    def test_files_get_module_name(self):
        """
        Test getting module name from path
        """
        files_view = FilesView()
        module = 'test-module'
        formatted_module_name = 'test/module'
        module_name = files_view._get_module_name(module)
        self.assertEqual(formatted_module_name, module_name)

    def test_files_get_module_slug_name(self):
        """
        Test getting module slug from path
        """
        files_view = FilesView()
        module = 'test-module'
        path = '/v3/files/test-module-1.2.3.tar.gz'
        module_name = files_view._get_module_slug_name(path)
        self.assertEqual(module, module_name)

    def test_files_get_module_version(self):
        """
        Test getting module version from path
        """
        files_view = FilesView()
        version = '1.2.3'
        formatted_module_name = 'module'
        path = '/v3/files/test-module-1.2.3.tar.gz'
        get_version = files_view._get_module_version(path)
        self.assertEqual(version, get_version)


class TestFilesPost36View(unittest.TestCase):
    """
    Tests for FilesView.
    """

    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.files.FilesView._get_credentials')
    def test_files_redirect_response(self, mock_get_credentials, mock_get_module_name):
        mock_get_module_name.return_value = 'foo/bar'
        file = FilesPost36View()
        module = 'foo/bar'
        get_dict = {'module': module}
        module_list_fixture = {'foo/bar': [
            {'file': 'http://example.com/foo-bar-1.2.3.tar.gz'},
        ]}
        response = file.get_redirect_response(module_list_fixture, 'foo/bar')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.get('location'), 'http://example.com/foo-bar-1.2.3.tar.gz')
