"""
    SoftLayer.testing
    ~~~~~~~~~~~~~~~~~

    :license: MIT, see LICENSE for more details.
"""
# Disable pylint import error and too many methods error
# pylint: disable=F0401,R0904
import logging
import os.path

import SoftLayer
from SoftLayer.CLI import core
from SoftLayer.CLI import environment

from click import testing
import mock
import testtools

FIXTURE_PATH = os.path.abspath(os.path.join(__file__, '..', 'fixtures'))


class MockableTransport(object):
    """Transport which is able to mock out specific API calls."""

    def __init__(self, transport):
        self.calls = []
        self.mocked = {}
        self.transport = transport

    def __call__(self, call):
        self._record_call(call)

        key = _mock_key(call.service, call.method)
        if key in self.mocked:
            return self.mocked[key](call)

        # Fall back to another transport (usually with fixtures)
        return self.transport(call)

    def set_mock(self, service, method):
        """Create a mock and return the mock object for the specific API call.

        :param service: API service to mock
        :param method: API method to mock
        """

        _mock = mock.MagicMock()
        self.mocked[_mock_key(service, method)] = _mock
        return _mock

    def _record_call(self, call):
        """Record and log the API call (for later assertions)."""
        self.calls.append(call)

        details = []
        for prop in ['identifier',
                     'args',
                     'mask',
                     'filter',
                     'limit',
                     'offset']:
            details.append('%s=%r' % (prop, getattr(call, prop)))

        logging.info('%s::%s called; %s',
                     call.service, call.method, '; '.join(details))


def _mock_key(service, method):
    """Key to address a mock object in MockableTransport."""
    return '%s::%s' % (service, method)


class TestCase(testtools.TestCase):
    """Testcase class with PEP-8 compatable method names."""

    def set_up(self):
        """Aliased from setUp."""
        pass

    def tear_down(self):
        """Aliased from tearDown."""
        pass

    def setUp(self):  # NOQA
        testtools.TestCase.setUp(self)

        # Create a crazy mockable, fixture client
        self.mocks = MockableTransport(SoftLayer.FixtureTransport())
        self.transport = SoftLayer.TimingTransport(self.mocks)
        self.client = SoftLayer.BaseClient(transport=self.transport)

        self.env = environment.Environment()
        self.env.client = self.client
        return self.set_up()

    def tearDown(self):  # NOQA
        testtools.TestCase.tearDown(self)
        return self.tear_down()

    def calls(self, service=None, method=None):
        """Return all API calls made during the current test."""

        conditions = []
        if service is not None:
            conditions.append(lambda call: call.service == service)
        if method is not None:
            conditions.append(lambda call: call.method == method)

        return [call for call in self.mocks.calls
                if all(cond(call) for cond in conditions)]

    def assert_called_with(self, service, method, **props):
        """Used to assert that API calls were called with given properties.

        Props are properties of the given transport.Request object.
        """

        for call in self.calls(service, method):
            if call_has_props(call, props):
                return

        raise AssertionError('%s::%s was not called with given properties: %s'
                             % (service, method, props))

    def set_mock(self, service, method):
        """Set and return mock on the current client."""
        return self.mocks.set_mock(service, method)

    def run_command(self,
                    args=None,
                    env=None,
                    fixtures=True,
                    fmt='json'):
        """A helper that runs a SoftLayer CLI command.

        This returns a click.testing.Result object.
        """
        args = args or []

        if fixtures is True:
            args.insert(0, '--fixtures')
        args.insert(0, '--format=%s' % fmt)

        runner = testing.CliRunner()
        return runner.invoke(core.cli, args=args, obj=env or self.env)


def call_has_props(call, props):
    """Check if a call has matching properties of a given props dictionary."""

    for prop, expected_value in props.items():
        actual_value = getattr(call, prop)
        if actual_value != expected_value:
            logging.info(
                '%s::%s property mismatch, %s: expected=%r; actual=%r',
                call.service,
                call.method,
                prop,
                expected_value,
                actual_value)
            return False

    return True
