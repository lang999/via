from __future__ import unicode_literals

import pytest

import json

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse as Response
from werkzeug import wsgi

from via.config_extractor import ConfigExtractor, pop_query_params_with_prefix


class TestPopQueryParamsWithPrefix(object):

    def test_it_ignores_non_matching_params(self, create_environ):
        environ = create_environ('one=1&two=2&three=3')
        orig_envion = environ.copy()

        params = pop_query_params_with_prefix(environ, 'aprefix.')

        assert params == {}
        assert environ == orig_envion

    def test_it_pops_matching_params(self, create_environ):
        environ = create_environ('one=1&two=2&aprefix.three=3&four=4')

        params = pop_query_params_with_prefix(environ, 'aprefix.')

        expected_environ = create_environ('one=1&two=2&four=4')
        assert params == {'aprefix.three': '3'}
        assert environ == expected_environ

    @pytest.fixture
    def create_environ(self):
        def create(query_string):
            return {'QUERY_STRING': query_string,
                    'REQUEST_URI': 'http://example.com?{}'.format(query_string)}
        return create


class TestConfigExtractor(object):
    def test_it_sets_template_params_from_matching_query_params(self, client_get):
        resp = client_get('/example.com?q=foobar&'
                          'via.open_sidebar=1&'
                          'via.request_config_from_frame=https://lms.hypothes.is')

        template_params = json.loads(resp.data).get('pywb.template_params')
        assert template_params == {'h_open_sidebar': True,
                                   'h_request_config': 'https://lms.hypothes.is'}

    def test_it_passes_non_matching_query_params_to_upstream_app(self, client_get):
        resp = client_get('/example.com?q=foobar&via.open_sidebar=1')

        upstream_environ = json.loads(resp.data)
        assert upstream_environ['QUERY_STRING'] == 'q=foobar'
        assert upstream_environ['REQUEST_URI'] == '/example.com?q=foobar'

    @pytest.fixture
    def app(self):
        return ConfigExtractor(upstream_app)

    @pytest.fixture
    def client_get(self, app):
        def get(url):
            client = Client(app, Response)

            # `Client` does not set "REQUEST_URI" as an actual app would, so
            # set it manually.
            environ = {'REQUEST_URI': url}

            return client.get(url, environ_overrides=environ)
        return get


@wsgi.responder
def upstream_app(environ, start_response):
    class Encoder(json.JSONEncoder):
        def default(self, o):
            try:
                return json.JSONEncoder.default(self, o)
            except TypeError:
                # Ignore un-serializable fields.
                return None
    body = Encoder().encode(environ)
    return Response(body)