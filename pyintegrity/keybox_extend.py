# pyintegrity/keybox_extend.py

import logging
import os
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from . import adb, utils
from .constants import *
from .utils import Colors

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.x509.oid import NameOID
except ImportError:
    x509 = None

try:
    import cbor2
except ImportError:
    cbor2 = None

logger = logging.getLogger(__name__)


def setup_extend_parser(subparsers):
    """Adds arguments for the 'tee keybox extend' command."""
    parser_extend = subparsers.add_parser(
        'extend', help='Create a new CA keybox signed by an existing keybox.')
    parser_extend.add_argument(
        '--input', required=True, help='Path to the input keybox file to use for signing.')
    parser_extend.add_argument(
        '--output', required=True, help='Path to save the new CA keybox file.')

    sign_group = parser_extend.add_mutually_exclusive_group(required=True)
    sign_group.add_argument('--sign-with-ecdsa', action='store_true',
                            help='Use the ECDSA key from input to sign new certs.')
    sign_group.add_argument('--sign-with-rsa', action='store_true',
                            help='Use the RSA key from input to sign new certs.')

    parser_extend.add_argument(
        '--ecdsa-serial', help='Custom hex serial for the new ECDSA CA certificate.')
    parser_extend.add_argument(
        '--rsa-serial', help='Custom hex serial for the new RSA CA certificate.')
    parser_extend.add_argument(
        '--ecdsa-subject', help='Custom subject DN for the new ECDSA CA cert.')
    parser_extend.add_argument(
        '--rsa-subject', help='Custom subject DN for the new RSA CA cert.')
    parser_extend.add_argument(
        '--force', '-f', action='store_true', help='Overwrite output file if it exists.')
    parser_extend.set_defaults(func=handle_extend_ca)


def handle_extend_ca(args):
    """Main handler for the extend command."""
    if not x509:
        raise ImportError(
            "This feature requires 'cryptography'. Please run: pip install cryptography")

    if os.path.exists(args.output) and not args.force:
        raise FileExistsError(
            f"Output file '{args.output}' already exists. Use --force to overwrite.")

    logger.info(f"Loading signer keybox from: {args.input}")

    # 1. Load Input Keybox
    signer_key, signer_chain, signer_leaf_cert = _load_signer_keybox(
        args.input, 'ecdsa' if args.sign_with_ecdsa else 'rsa')

    # 2. Generate New Keypairs
    logger.info("Generating new ECDSA and RSA keypairs...")
    new_ecdsa_priv_key = ec.generate_private_key(ec.SECP256R1())
    new_rsa_priv_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048)

    # 3. Forge and Sign New CA Certificates
    logger.info("Forging and signing new CA certificates...")
    new_ecdsa_ca_cert = _create_ca_cert(
        subject_dn_str=args.ecdsa_subject,
        public_key=new_ecdsa_priv_key.public_key(),
        issuer_cert=signer_leaf_cert,
        signing_key=signer_key,
        serial_hex=args.ecdsa_serial
    )
    new_rsa_ca_cert = _create_ca_cert(
        subject_dn_str=args.rsa_subject,
        public_key=new_rsa_priv_key.public_key(),
        issuer_cert=signer_leaf_cert,
        signing_key=signer_key,
        serial_hex=args.rsa_serial
    )

    # 4. Assemble New Chains
    new_ecdsa_chain_certs = [new_ecdsa_ca_cert] + signer_chain
    new_rsa_chain_certs = [new_rsa_ca_cert] + signer_chain

    # 5. Construct Final Keybox
    logger.info("Constructing final CA keybox XML...")
    new_keybox_xml = _build_ca_keybox_xml(
        new_ecdsa_priv_key, new_ecdsa_chain_certs,
        new_rsa_priv_key, new_rsa_chain_certs
    )

    # 6. Save Output
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(new_keybox_xml)

    logger.info(
        f"{Colors.GREEN}Successfully created new CA keybox at: {args.output}{Colors.ENDC}")


def _load_signer_keybox(file_path, sign_algo):
    """Loads a keybox and extracts the specified signing key and its chain."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    tree = ET.parse(file_path)
    key_element = tree.find(f".//Key[@algorithm='{sign_algo}']")
    if key_element is None:
        raise RuntimeError(
            f"Input keybox does not contain a private key for algorithm '{sign_algo}'.")

    priv_key_pem = key_element.find('.//PrivateKey').text
    private_key = serialization.load_pem_private_key(
        priv_key_pem.encode('utf-8'), password=None)

    chain_elements = key_element.findall('.//Certificate')
    cert_chain = [x509.load_pem_x509_certificate(
        c.text.encode('utf-8')) for c in chain_elements]

    return private_key, cert_chain, cert_chain[0]  # key, full chain, leaf cert


def _create_ca_cert(subject_dn_str, public_key, issuer_cert, signing_key, serial_hex):
    """Creates a single, signed CA certificate."""
    if not cbor2:
        raise ImportError(
            "This feature requires 'cbor2'. Please run: pip install cbor2")

    if subject_dn_str:
        subject = x509.Name.from_rfc4514_string(subject_dn_str)
    else:
        subject = x509.Name([
            x509.NameAttribute(NameOID.TITLE, "TEE"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER,
                               f"{random.getrandbits(128):x}")
        ])

    serial_number = int(
        serial_hex, 16) if serial_hex else x509.random_serial_number()

    builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer_cert.subject
    ).public_key(
        public_key
    ).serial_number(
        serial_number
    ).not_valid_before(
        datetime.now(timezone.utc) - timedelta(days=200)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=365*10)
    )

    #  Add Subject Key Identifier (SKI) for the new certificate.
    #    This is a hash of the new certificate's own public key.
    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(public_key),
        critical=False
    )

    #  Add Authority Key Identifier (AKI) pointing to the signer.
    #    This must match the SKI of the certificate that is signing this one.
    try:
        # The correct way is to get the SKI from the issuer's extensions.
        issuer_ski = issuer_cert.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier)
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                issuer_ski.value),
            critical=False
        )
    except x509.ExtensionNotFound:
        # Fallback if the issuer cert doesn't have an SKI (unlikely for a keybox cert).
        # We can generate it from the issuer's public key instead.
        logger.warning(
            "Issuer certificate is missing SubjectKeyIdentifier. Generating AKI from issuer's public key.")
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                issuer_cert.public_key()),
            critical=False
        )

    #  Add Basic Constraints and Key Usage.
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).add_extension(
        x509.KeyUsage(key_cert_sign=True, crl_sign=False, digital_signature=False,
                      content_commitment=False, key_encipherment=False, data_encipherment=False,
                      key_agreement=False, encipher_only=False, decipher_only=False),
        critical=True
    )

    #  Forge the ProvisioningInfo CBOR payload.
    #    Key 1: certsIssued (Integer)
    #    Key 3: manufacturer (String)
    provisioning_info_payload = {
        1: random.randint(5, 60),  # Use a realistic-looking random number
        3: "Google"
    }
    cbor_bytes = cbor2.dumps(provisioning_info_payload)

    #  Create the custom X.509 extension object.
    #    The OID is 1.3.6.1.4.1.11129.2.1.30 for ProvisioningInfo.
    provisioning_extension = x509.UnrecognizedExtension(
        oid=x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.1.30"),
        value=cbor_bytes
    )

    builder = builder.add_extension(provisioning_extension, critical=False)
    return builder.sign(signing_key, hashes.SHA256())


def _generate_cert_chain_xml(cert_chain):
    """
    Correctly generates the XML block for a certificate chain,
    including the NumberOfCertificates tag and individual Certificate tags.
    """
    # 1. Start with the NumberOfCertificates tag.
    num_certs = len(cert_chain)
    xml_parts = [
        f"\t\t\t\t<NumberOfCertificates>{num_certs}</NumberOfCertificates>\n"]

    # 2. Iterate and wrap each certificate individually.
    for cert in cert_chain:
        pem_bytes = cert.public_bytes(serialization.Encoding.PEM)
        pem_string = pem_bytes.decode('utf-8').strip()
        xml_parts.append(
            f'\t\t\t\t<Certificate format="pem">\n{pem_string}\n\t\t\t\t</Certificate>\n')

    # Join without newlines, as the PEM format already has them.
    return "".join(xml_parts)


def _build_ca_keybox_xml(ecdsa_priv, ecdsa_chain, rsa_priv, rsa_chain):
    """Constructs the final XML string for the new CA keybox."""

    # Helper to get the raw PEM string
    def format_pem(data):
        return data.decode('utf-8').strip()

    # Get PEM strings for the private keys
    ecdsa_priv_pem = format_pem(ecdsa_priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))
    rsa_priv_pem = format_pem(rsa_priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

    # Generate the correctly formatted XML blocks for each certificate chain
    ecdsa_certs_xml = _generate_cert_chain_xml(ecdsa_chain)
    rsa_certs_xml = _generate_cert_chain_xml(rsa_chain)

    # Use an f-string to build the final, well-structured XML
    return f"""<?xml version="1.0"?>
<AndroidAttestation>
\t<Keybox DeviceID="generated-ca">
\t\t<Key algorithm="ecdsa">
\t\t\t<PrivateKey format="pem">
{ecdsa_priv_pem}
\t\t\t</PrivateKey>
\t\t\t<CertificateChain>
{ecdsa_certs_xml}\t\t\t</CertificateChain>
\t\t</Key>
\t\t\t<Key algorithm="rsa">
\t\t\t<PrivateKey format="pem">\n{rsa_priv_pem}
\t\t\t</PrivateKey>
\t\t\t<CertificateChain>
{rsa_certs_xml}\t\t\t</CertificateChain>
\t\t</Key>
\t</Keybox>
</AndroidAttestation>
"""
