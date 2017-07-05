import json
import logging

from jwkest import as_unicode
from jwkest.jws import factory
from six import PY2
from six import string_types

from oic.utils.keyio import KeyJar

from oic.oauth2.message import SINGLE_OPTIONAL_STRING
from oic.oauth2.exception import VerificationError
from oic.oauth2.message import OPTIONAL_LIST_OF_STRINGS

from oic.oic import message
from oic.oic.message import JasonWebToken
from oic.oic.message import OPTIONAL_MESSAGE
from oic.oic.message import RegistrationRequest

logger = logging.getLogger(__name__)

__author__ = 'roland'
__version__ = '0.3.1'

#: Contexts in which metadata statements can be used
CONTEXTS = ['registration', 'discovery', 'response']

MIN_SET = dict([(k, {}) for k in CONTEXTS])


class MetadataStatementError(Exception):
    pass


class MetadataStatement(JasonWebToken):
    """
    A base class for metadata statements
    """
    c_param = JasonWebToken.c_param.copy()
    c_param.update({
        "signing_keys": SINGLE_OPTIONAL_STRING,
        'signing_keys_uri': SINGLE_OPTIONAL_STRING,
        'metadata_statements': OPTIONAL_MESSAGE,
        'metadata_statement_uris': OPTIONAL_MESSAGE,
        'signed_jwks_uri': SINGLE_OPTIONAL_STRING,
        'federation_usage': SINGLE_OPTIONAL_STRING
    })

    def verify(self, **kwargs):
        """
        Verifies that an instance of this class adhers to the given 
            restrictions.
        """
        super(MetadataStatement, self).verify(**kwargs)
        if "signing_keys" in self:
            if 'signing_keys_uri' in self:
                raise VerificationError(
                    'You can only have one of "signing_keys" and '
                    '"signing_keys_uri" in a metadata statement')
            else:
                # signing_keys MUST be a JWKS
                kj = KeyJar()
                try:
                    kj.import_jwks(self['signing_keys'], '')
                except Exception:
                    raise VerificationError('"signing_keys" not a proper JWKS')

        if "metadata_statements" in self and "metadata_statement_uris" in self:
            s = set(self['metadata_statements'].keys())
            t = set(self['metadata_statement_uris'].keys())
            if s.intersection(t):
                raise VerificationError(
                    'You should not have the same key in "metadata_statements" '
                    'and in "metadata_statement_uris"')

        return True


class ClientMetadataStatement(MetadataStatement):
    """
    A Client registration Metadata statement.
    """
    c_param = MetadataStatement.c_param.copy()
    c_param.update(RegistrationRequest.c_param.copy())
    c_param.update({
        "scope": OPTIONAL_LIST_OF_STRINGS,
        'claims': OPTIONAL_LIST_OF_STRINGS,
    })


class ProviderConfigurationResponse(message.ProviderConfigurationResponse):
    """
    A Provider info metadata statement
    """
    c_param = MetadataStatement.c_param.copy()
    c_param.update(message.ProviderConfigurationResponse.c_param.copy())


def unfurl(jwt):
    """
    Return the body of a signed JWT, without verifying the signature.
    
    :param jwt: A signed JWT 
    :return: The body of the JWT as a 'UTF-8' string
    """

    _rp_jwt = factory(jwt)
    return json.loads(_rp_jwt.jwt.part[1].decode('utf8'))


def keyjar_from_metadata_statements(iss, msl):
    """
    Builds a keyJar instance based on the information in the 'signing_keys'
    claims in a list of metadata statements.
    
    :param iss: Owner of the signing keys 
    :param msl: List of :py:class:`MetadataStatement` instances.
    :return: A oic.utils.keyio.KeyJar instance
    """
    keyjar = KeyJar()
    for ms in msl:
        keyjar.import_jwks(ms['signing_keys'], iss)
    return keyjar


def read_jwks_file(jwks_file):
    """
    Reads a file containing a JWKS and populates a oic.utils.keyio.KeyJar from
    it.

    :param jwks_file: file name of the JWKS file 
    :return: A oic.utils.keyio.KeyJar instance
    """
    _jwks = open(jwks_file, 'r').read()
    _kj = KeyJar()
    _kj.import_jwks(json.loads(_jwks), '')
    return _kj


def is_lesser(a, b):
    """
    Verify that a is <= then b
    
    :param a: An item
    :param b: Another item
    :return: True or False
    """

    if type(a) != type(b):
        if PY2:  # one might be unicode and the other str
            return as_unicode(a) == as_unicode(b)

        return False

    if isinstance(a, string_types) and isinstance(b, string_types):
        return a == b
    elif isinstance(a, bool) and isinstance(b, bool):
        return a == b
    elif isinstance(a, list) and isinstance(b, list):
        for element in a:
            flag = 0
            for e in b:
                if is_lesser(element, e):
                    flag = 1
                    break
            if not flag:
                return False
        return True
    elif isinstance(a, dict) and isinstance(b, dict):
        if is_lesser(list(a.keys()), list(b.keys())):
            for key, val in a.items():
                if not is_lesser(val, b[key]):
                    return False
            return True
        return False
    elif isinstance(a, int) and isinstance(b, int):
        return a <= b
    elif isinstance(a, float) and isinstance(b, float):
        return a <= b

    return False


#: When flattening a grounded metadata statement these claims should be ignored.
IgnoreKeys = list(JasonWebToken.c_param.keys())

#: When comparing metadata statement these claims should be ignored.
DoNotCompare = list(set(MetadataStatement.c_param.keys()).difference(IgnoreKeys))
DoNotCompare.append('kid')
