import base64
import re
import urllib

from django.http import HttpResponseNotFound, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.views.generic import View

from pulp_puppet.forge import releases
from pulp.server.webservices.views.util import generate_json_response

MODULE_PATTERN = re.compile('(^[a-zA-Z0-9]+)(/|-)([a-zA-Z0-9_]+)$')


class AbstractForgeView(View):

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

        module_name = self._get_module_name(request.GET)
        if not module_name:
            return HttpResponseBadRequest('Module name is missing.')
        version = request.GET.get('version')

        data = self.get_releases(*credentials, module_name=module_name, version=version,
                                 hostname=hostname)
        if isinstance(data, HttpResponse):
            return data
        return self.format_results(data, request.GET, request.path_info)

    def get_releases(self, *args, **kwargs):
        """
        Get the list of matching releases

        :return: The matching modules
        :rtype: dict
        """
        return releases.view(*args, **kwargs)

    def format_results(self, data, get_dict, path):
        """
        Format the results and begin streaming out to the caller

        :param data: The module data to stream back to the caller
        :type data: dict
        :param get_dict: The GET parameters
        :type get_dict: dict
        :return: the body of what should be streamed out to the caller
        :rtype: str
        """
        return generate_json_response(data)

    @staticmethod
    def _get_credentials(headers):
        """
        :return: username and password provided as basic auth credentials
        :rtype:  str, str
        """
        auth = headers.get('HTTP_AUTHORIZATION')
        if auth:
            encoded_credentials = re.sub('^Basic ', '', auth)
            try:
                username, password = base64.decodestring(encoded_credentials).split(':')
            # raised by the split if the decoded string lacks a ':'
            except ValueError:
                return
            return username, password