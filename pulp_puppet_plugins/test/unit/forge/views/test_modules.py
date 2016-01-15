import json
import unittest
import base64

import mock
from pulp_puppet.forge.views.modules import ModulesView, ModulesPost36View


class TestModulesView(unittest.TestCase):
    """
    Tests for ModulesView.
    """

    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_credentials')
    def test_releases_missing_module(self, mock_get_credentials, mock_get_module_name):
        """
        Test that proper response is returned when module name is not specified
        """
        mock_get_module_name.return_value = ''
        mock_get_credentials.return_value = ()
        mock_request = mock.MagicMock()

        releases_view = ModulesView()
        response = releases_view.get(mock_request, resource_type='repository', resource='repo-id')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'Module name is missing.')

    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_credentials')
    def test_releases_missing_auth(self, mock_get_credentials, mock_get_module_name):
        """
        Test that 401 is returned when basic auth is not used for pre 3.3
        """
        mock_get_module_name.return_value = 'fake-module'
        mock_get_credentials.return_value = ()
        mock_request = mock.MagicMock()

        releases_view = ModulesView()
        response = releases_view.get(mock_request)
        self.assertEqual(response.status_code, 401)

    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_credentials')
    def test_releases_bad_resource_type(self, mock_get_credentials, mock_get_module_name):
        """
        Test that only consumer or repository resource type is allowed
        """
        mock_get_module_name.return_value = 'fake-module'
        mock_get_credentials.return_value = ()
        mock_request = mock.MagicMock()

        releases_view = ModulesView()
        response = releases_view.get(mock_request, resource_type='foo')
        self.assertEqual(response.status_code, 404)

    def test_releases_get_credentials(self):
        """
        Test getting credentials from header
        """
        releases_view = ModulesView()
        real_creds = ('test', '123')
        encoded_creds = base64.encodestring('test:123')
        headers = {'HTTP_AUTHORIZATION': encoded_creds}
        creds = releases_view._get_credentials(headers)
        self.assertEqual(real_creds, creds)

    def test_releases_get_bad_credentials(self):
        """
        Test getting improperly formatted credentials from header
        """
        releases_view = ModulesView()
        encoded_creds = base64.encodestring('blah')
        headers = {'HTTP_AUTHORIZATION': encoded_creds}
        creds = releases_view._get_credentials(headers)
        self.assertEqual(creds, None)

    def test_releases_get_module_name(self):
        """
        Test getting module name from path
        """
        releases_view = ModulesView()
        module = 'test/module'
        path = '/v3/modules/test-module'
        module_name = releases_view._get_module_name(path)
        self.assertEqual(module, module_name)

    def test_releases_get_module_author(self):
        """
        Test getting module author from path
        """
        releases_view = ModulesView()
        module_name = 'test/module'
        author = 'test'
        author_name = releases_view._get_module_author(module_name)
        self.assertEqual(author, author_name)


class TestModulesPost36View(unittest.TestCase):
    """
    Tests for ModulesView.
    """
    FAKE_VIEW_DATA = {'foo/bar': [{'version': '1.0.0', 'file': '/tmp/foo', 'dependencies': []}]}
    RESULT_FIXTURE = {}
    RESPONSE_FIXTURE = {
        "module_group": "base",
        "current_release": {
            "file_uri": "/pulp/puppet/puppetforge/system/releases/p/puppetlabs/puppetlabs-java-1.4.3.tar.gz",
            "module": {
                "owner": {
                    "username": "puppetlabs",
                    "slug": "puppetlabs"
                },
                "uri": "/v3/modules/puppetlabs-java",
                "name": "java",
                "slug": "puppetlabs-java"
            },
            "file_md5": "279c67da26f4a5878c53ff432d4a73ce",
            "version": "1.4.3",
            "slug": "puppetlabs-java-1.4.3",
            "metadata": {
                "version": "1.4.3",
                "name": "puppetlabs-java",
                "dependencies": [{
                    "name": "puppetlabs/stdlib",
                    "version_requirement": ">= 2.4.0 < 5.0.0"
                }]
            }
        },
        "name": "java",
        "releases": [{
            "created_at": None,
            "supported": False,
            "uri": "/v3/releases/puppetlabs-java-1.4.3",
            "version": "1.4.3",
            "deleted_at": None,
            "slug": "puppetlabs-java-1.4.3"
        }],
        "endorsement": None,
        "updated_at": "2016-01-06 12:58:15 -0800",
        "created_at": "2015-09-11 07:22:37 -0700",
        "uri": "/v3/modules/puppetlabs-java",
        "slug": "puppetlabs-java"
    }

    @mock.patch('pulp_puppet.forge.views.modules.ModulesPost36View._get_module_name')
    def test_format_results_render_module(self, mock_get_module_name):
        mock_get_module_name.return_value = 'puppetlabs/java'
        release = ModulesPost36View()
        module = 'puppetlabs/java'
        get_dict = {}
        result_str = release.format_results(self.RESULT_FIXTURE, get_dict, '/v3/modules/puppetlabs-java', module).content
        result = json.loads(result_str)

        module_data = result['results'][0]
        self.assertEquals('foo/bar', module_data['metadata']['name'])
        self.assertEquals('1.0', module_data['metadata']['version'])
        self.assertEquals('foo', module_data['file_uri'])
        self.assertEquals('bar', module_data['file_md5'])
        dependencies = module_data['metadata']['dependencies']
        self.assertEquals('apple', dependencies[0]['name'])
        self.assertEquals('42.5', dependencies[0]['version_requirement'])

    @mock.patch('pulp_puppet.forge.releases.view')
    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_module_name')
    @mock.patch('pulp_puppet.forge.views.modules.ModulesView._get_credentials')
    def test_releases_get_module_without_version(self, mock_get_credentials, mock_get_module_name,
                                                 mock_view):
        """
        Test getting a module without specifying a version
        """
        mock_get_module_name.return_value = 'foo/bar'
        mock_get_credentials.return_value = ('consumer1', 'repo1')
        mock_request = mock.MagicMock()
        mock_view.return_value = self.FAKE_VIEW_DATA

        releases_view = ModulesPost36View()
        response = releases_view.get(mock_request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, json.dumps(self.FAKE_VIEW_DATA))
