import re
import urllib

from django.http import HttpResponseNotFound, HttpResponse, HttpResponseBadRequest

from pulp.server.webservices.views.util import generate_json_response

from pulp_puppet.forge import releases
from pulp_puppet.forge.views.abstract import AbstractForgeView

from distutils.version import StrictVersion

MODULE_PATTERN = re.compile('(^[a-zA-Z0-9]+)(/|-)([a-zA-Z0-9_]+)$')


class ModulesView(AbstractForgeView):

    REPO_RESOURCE = 'repository'
    CONSUMER_RESOURCE = 'consumer'

    def get(self, request, resource_type=None, resource=None):
        """
        Credentials here are not actually used for authorization, but instead
        are used to identify:

            consumer ID in the username field
            repository ID in the password field

        This is to work around the fact that the "puppet module install"
        command has hard-coded absolute paths, so we cannot put consumer or
        repository IDs in the URL's path.
        """
        hostname = request.get_host()
        if resource_type is not None:
            if resource_type == self.REPO_RESOURCE:
                credentials = ('.', resource)
            elif resource_type == self.CONSUMER_RESOURCE:
                credentials = (resource, '.')
            else:
                return HttpResponseNotFound()

        else:
            credentials = self._get_credentials(request.META)
            if not credentials:
                return HttpResponse('Unauthorized', status=401)

        module_name = self._get_module_name(request.path)
        if not module_name:
            return HttpResponseBadRequest('Module name is missing.')
        version = request.GET.get('version')

        data = self.get_releases(*credentials, module_name=module_name, version=version,
                                 hostname=hostname)
        if isinstance(data, HttpResponse):
            return data

        return self.format_results(data, request.GET, request.path_info, module_name)

    @staticmethod
    def _get_module_name(path):
        """
        :return: name of the module being requested, or None if not found or invalid
        """
        splitpaths = path.split('/')
        module_name = splitpaths[3]
        match = MODULE_PATTERN.match(module_name)
        if match:
            normalized_name = u'%s/%s' % (match.group(1), match.group(3))
            return normalized_name

    @staticmethod
    def _get_module_author(module_name):
        """
        :return: author of the module being requested, or None if not found or invalid
        """
        splitpaths = module_name.split('/')
        return splitpaths[0]


class ModulesPost36View(ModulesView):

    @staticmethod
    def _format_query_string(base_url, module_name, module_version, offset, limit):
        """
        Build the query string to be used for creating

        :param base_url: The context root to sue when generating a releases query.
        :type base_url: str
        :param module_name: The module name to add to the query string
        :type module_name: str
        :param module_version: The version of the module to encode in the query string
        :type module_version: str
        :param offset: The offset to encode for pagination
        :type offset: int
        :param limit: The max number of items to show on a page
        :type limit: int
        :return: The encoded URL for the specified query arguments
        :rtype: str
        """
        query_args = {'module': module_name,
                      'offset': offset,
                      'limit': limit}
        if module_version:
            query_args['version'] = module_version

        return '%s?%s' % (base_url, urllib.urlencode(query_args))

    def get_releases(self, *args, **kwargs):
        """
        Get the list of matching releases

        :return: The matching modules
        :rtype: dict
        """
        return releases.view(*args, recurse_deps=False, view_all_matching=True, **kwargs)

    def format_results(self, data, get_dict, path, module_name):
        """
        Format the results and begin streaming out to the caller for the v3 API

        :param data: The module data to stream back to the caller
        :type data: dict
        :param get_dict: The GET parameters
        :type get_dict: dict
        :param path: The path starting with parameters
        :type path: str
        :param module_name: The module name with author
        :type module_name: unicode
        :return: the body of what should be streamed out to the caller
        :rtype: str
        """
        # module_name = get_dict.get('module', '')
        # clean_name = self._get_module_name(module_name)
        clean_name = module_name.split('/')[1]
        clean_author = self._get_module_author(module_name)
        module_slug = clean_author + '-' + clean_name

        formatted_results = {
            'uri': '/v3/modules/' + module_slug,
            'slug': module_slug,
            'name': clean_name,
            'created_at': '2015-09-11 07:22:37 -0700',
            'updated_at': '2016-01-06 12:58:15 -0800',
            # 'supported': false,
            'endorsement': None,
            'module_group': 'base',
            'current_release': {
                'module': {
                    'uri': '/v3/modules/' + module_slug,
                    'slug': module_slug,
                    'name': clean_name,
                    'owner': {
                        'slug': clean_author,
                        'username': clean_author
                    }
                },
            },
            'releases': []

        }

        module_list = data.get(module_name)

        versions = []
        module_data = {}
        for module in module_list:
            formatted_dependencies = []
            for dep in module.get('dependencies', []):
                formatted_dependencies.append({
                    'name': dep[0],
                    'version_requirement': dep[1]
                })

            versions.append(module.get('version'))
            module_data[module.get('version')] = {
                'metadata': {
                    'name': module_slug,
                    'version': module.get('version'),
                    'dependencies': formatted_dependencies
                },
                'file_uri': module.get('file'),
                'file_md5': module.get('file_md5'),
                'version': module.get('version'),
                'slug': module_slug + '-' + module.get('version')
            }

        versions.sort(key=StrictVersion)
        current_version = versions.pop()

        for attribute, value in module_data[current_version].iteritems():
            formatted_results['current_release'][attribute] = value

        release_data = []
        for version, module in module_data.iteritems():
            release_data.append({
                'uri': '/v3/releases/' + str(module['slug']),
                'slug':  module['slug'],
                'version': version,
                'supported': False,
                'created_at': None,
                'deleted_at': None
            })

        formatted_results['releases'] = release_data

        return generate_json_response(formatted_results)