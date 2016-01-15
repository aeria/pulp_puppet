import base64
import re
import urllib

from django.http import HttpResponseNotFound, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect

from pulp_puppet.forge import releases
from pulp.server.webservices.views.util import generate_json_response
from pulp_puppet.forge.views.abstract import AbstractForgeView

MODULE_PATTERN = re.compile('(^[a-zA-Z0-9]+)(/|-)([a-zA-Z0-9_]+)$')


class FilesView(AbstractForgeView):

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

        module_slug_name = self._get_module_slug_name(request.path)
        module_name = self._get_module_name(module_slug_name)
        if not module_name:
            return HttpResponseBadRequest('Module name is missing.')

        version = self._get_module_version(request.path)

        data = self.get_releases(*credentials, module_name=module_name, version=version,
                                 hostname=hostname)

        if not data:
            return HttpResponseNotFound('Module not found')

        return self.get_redirect_response(data, module_name)

    def get_redirect_response(self, data, module_name):
        """
        Get the response given the matched module.

        :return: HTTP Response redirecting to download the file, or 404
        :rtype: HttpResponseRedirect|HttpResponseNotFound
        """
        module_list = data.get(module_name)

        for module in module_list:
            return HttpResponseRedirect(str(module['file']))

        return HttpResponseNotFound('No matching version file found')

    @staticmethod
    def _get_module_name(module_name):
        """
        :return: name of the module being requested, or None if not found or invalid
        """

        match = MODULE_PATTERN.match(module_name)
        if match:
            normalized_name = u'%s/%s' % (match.group(1), match.group(3))
            return normalized_name

    @staticmethod
    def _get_module_slug_name(path):
        """
        :return: name of the module being requested, or None if not found or invalid
        """
        splitpaths = path.split('/')
        module = splitpaths[3]
        module_version = module.split('-')[2]
        module_name = module.replace('-' + module_version, '')
        return module_name

    @staticmethod
    def _get_module_version(path):
        """
        :return: name of the module being requested, or None if not found or invalid
        """
        splitpaths = path.split('/')
        module = splitpaths[3]
        module_version = module.split('-')[2]
        module_version_clean = module_version.replace('.tar.gz', '')
        return module_version_clean


class FilesPost36View(FilesView):

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
