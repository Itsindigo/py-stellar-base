# coding:utf-8
import base64
import os
import warnings

from .base58 import b58decode_check, b58encode_check
from .stellarxdr import Xdr
from .utils import XdrLengthError, decode_check, encode_check, StellarMnemonic

# noinspection PyBroadException
try:
    # noinspection PyUnresolvedReferences
    from pure25519 import ed25519_oop as ed25519
except ImportError:
    import ed25519
import hashlib


class Keypair(object):
    """The :class:`Keypair` object, which represents a signing and
    verifying key for use with the Stellar network.

    Instead of instantiating the class directly, we recommend using one of
    several class methods:

    * :meth:`Keypair.random`
    * :meth:`Keypair.deterministic`
    * :meth:`Keypair.from_seed`
    * :meth:`Keypair.from_address`

    :param verifying_key: The verifying (public) Ed25519 key in the keypair.
    :type verifying_key: ed25519.VerifyingKey
    :param signing_key: The signing (private) Ed25519 key in the keypair.
    :type signing_key: ed25519.SigningKey

    """

    def __init__(self, verifying_key, signing_key=None):
        # FIXME: Throw more specific exceptions instead of assert statements.
        assert type(verifying_key) is ed25519.VerifyingKey
        self.verifying_key = verifying_key
        if self.signing_key is not None:
            assert type(signing_key) is ed25519.SigningKey
            self.signing_key = signing_key

    @classmethod
    def deterministic(cls, mnemonic, passphrase='', lang='english', index=0):
        """Generate a :class:`Keypair` object via a deterministic
        phrase.

        Using a mnemonic, such as one generated from :class:`StellarMnemonic`,
        generate a new keypair deterministically. Uses :class:`StellarMnemonic`
        internally to generate the seed from the mnemonic, using PBKDF2.

        :param str mnemonic: A unique string used to deterministically generate
            keypairs.
        :param str passphrase: An optional passphrase used as part of the salt
            during PBKDF2 rounds when generating the seed from the mnemonic.
        :param str lang: The language of the mnemonic, defaults to english.
        :param int index: The index of the keypair generated by the mnemonic.
            This allows for multiple Keypairs to be derived from the same
            mnemonic, such as::

                >>> from stellar_base import Keypair
                >>> m = 'hello world'  # Don't use this mnemonic in practice.
                >>> kp1 = Keypair.deterministic(m, lang='english', index=0)
                >>> kp2 = Keypair.deterministic(m, lang='english', index=1)
                >>> kp3 = Keypair.deterministic(m, lang='english', index=2)

        :return: A new :class:`Keypair` instance derived from the mnemonic.

        """
        sm = StellarMnemonic(lang)
        seed = sm.to_seed(mnemonic, passphrase=passphrase, index=index)
        return cls.from_raw_seed(seed)

    @classmethod
    def random(cls):
        """Generate a :class:`Keypair` object via a randomly generated seed."""
        seed = os.urandom(32)
        return cls.from_raw_seed(seed)

    @classmethod
    def from_seed(cls, seed):
        """Generate a :class:`Keypair` object via a strkey encoded seed.

        :param str seed: A base32 encoded secret seed string encoded as
            described in :func:`encode_check`.
        :return: A new :class:`Keypair` instance derived by the secret seed.

        """
        raw_seed = decode_check("seed", seed)
        return cls.from_raw_seed(raw_seed)

    @classmethod
    def from_raw_seed(cls, raw_seed):
        """Generate a :class:`Keypair` object via a sequence of bytes.

        Typically these bytes are random, such as the usage of
        :func:`os.urandom` in :meth:`Keypair.random`. However this class method
        allows you to use an arbitrary sequence of bytes, provided the sequence
        is 32 bytes long.

        :param bytes raw_seed: A bytes object used as the seed for generating
            the keypair.
        :return: A new :class:`Keypair` derived by the raw secret seed.

        """
        signing_key = ed25519.SigningKey(raw_seed)
        verifying_key = signing_key.get_verifying_key()
        return cls(verifying_key, signing_key)

    @classmethod
    def from_base58_seed(cls, base58_seed):
        """Generate a :class:`Keypair` object via Base58 encoded seed.

        .. deprecated:: 0.1.7
           Base58 address encoding is DEPRECATED! Use this method only for
           transition to strkey encoding.

        :param str base58_seed: A base58 encoded encoded secret seed.
        :return: A new :class:`Keypair` derived from the secret seed.

        """
        warnings.warn(
            "Base58 address encoding is DEPRECATED! Use this method only for "
            "transition to strkey encoding.", DeprecationWarning)
        raw_seed = b58decode_check(base58_seed)[1:]
        return cls.from_raw_seed(raw_seed)

    @classmethod
    def from_address(cls, address):
        """Generate a :class:`Keypair` object via a strkey encoded public key.

        :param str address: A base32 encoded public key encoded as described in
            :func:`encode_check`
        :return: A new :class:`Keypair` with only a verifying (public) key.

        """
        public_key = decode_check("account", address)
        if len(public_key) != 32:
            raise XdrLengthError('Invalid Stellar address')
        verifying_key = ed25519.VerifyingKey(public_key)
        return cls(verifying_key)

    # TODO: Make some of the following functions properties?

    # TODO: Make this function private, given its use in xdr(self).
    def account_xdr_object(self):
        """Create PublicKey XDR object via public key bytes.

        :return: Serialized XDR of PublicKey type.
        """
        return Xdr.types.PublicKey(Xdr.const.KEY_TYPE_ED25519,
                                   self.verifying_key.to_bytes())

    def xdr(self):
        """Generate base64 encoded XDR PublicKey object.

        Return a base64 encoded PublicKey XDR object, for sending over the wire
        when interacting with stellard.

        :return: The base64 encoded PublicKey XDR structure.
        """
        kp = Xdr.StellarXDRPacker()
        kp.pack_PublicKey(self.account_xdr_object())
        return base64.b64encode(kp.get_buffer())

    def public_key(self):
        """See :meth:`Keypair.account_xdr_object`."""
        return self.account_xdr_object()

    def raw_public_key(self):
        """Get the bytes that comprise the verifying (public) key.

        :return: The verifying key's bytes.

        """
        return self.verifying_key.to_bytes()

    def raw_seed(self):
        """Get the bytes of the signing key's seed.

        :return: The signing key's secret seed as a byte sequence.
        :rtype: bytes
        """
        return self.signing_key.to_seed()

    def address(self):
        """Get the public key encoded as a strkey.

        See :func:`encode_check` for more details on the strkey encoding
        process.

        :return: The public key encoded as a strkey.
        :rtype: str
        """
        return encode_check('account', self.raw_public_key())

    def seed(self):
        """Get the secret seed encoded as a strkey.

        See :func:`encode_check` for more details on the strkey encoding
        process.

        :return: The secret seed encoded as a strkey.
        :rtype: str
        """
        return encode_check('seed', self.raw_seed())

    def sign(self, data):
        """Sign a bytes-like object using the signing (private) key.

        :return: The signed data
        :rtype: bytes
        """
        # FIXME: Refactor this method into more robust exception handling.
        try:
            return self.signing_key.sign(data)
        except:
            raise Exception("cannot sign: no secret key available")

    def verify(self, data, signature):
        """Verify the signature of a sequence of bytes.

        Verify the signature of a sequence of bytes using the verifying
        (public) key and the data that was originally signed, otherwise throws
        an exception.

        :param bytes data: A sequence of bytes that were previously signed by
            the private key associated with this verifying key.
        :param bytes signature: A sequence of bytes that comprised the
            signature for the corresponding data.
        """

        return self.verifying_key.verify(signature, data)

    def sign_decorated(self, data):
        signature = self.sign(data)
        hint = self.signature_hint()
        return Xdr.types.DecoratedSignature(hint, signature)

    def signature_hint(self):
        return bytes(self.public_key().ed25519[-4:])

    def to_old_address(self):
        rv = hashlib.new('sha256', self.raw_public_key()).digest()
        rv = hashlib.new('ripemd160', rv).digest()
        rv = chr(0).encode() + rv
        # v += hashlib.new(
        #     'sha256', hashlib.new('sha256', rv).digest()).digest()[0:4]
        return b58encode_check(rv)

    def to_old_seed(self):
        seed = chr(33).encode() + self.raw_seed()
        return b58encode_check(seed)
