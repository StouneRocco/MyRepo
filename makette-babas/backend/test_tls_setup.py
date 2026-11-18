import base64
import hashlib
import tempfile
import unittest
import os
from pathlib import Path

from tls_setup import create_certificate_app, certificate_fingerprint, load_tls_settings


class TlsSettingsTests(unittest.TestCase):
    def test_direct_start_discovers_local_certificates_and_bom_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('server-cert.pem','server-key.pem','maquette-ca.crt'):
                (root/name).write_text('test')
            (root/'config.json').write_text('{"hostAddress":"10.21.23.100"}',encoding='utf-8-sig')
            settings=load_tls_settings(root,{})
            self.assertEqual(settings['certificate'],str((root/'server-cert.pem').resolve()))
            self.assertEqual(settings['key'],str((root/'server-key.pem').resolve()))
            self.assertEqual(settings['host'],'10.21.23.100')
            self.assertTrue(settings['ca'].endswith('maquette-ca.crt'))

    def test_incomplete_configuration_never_silently_downgrades_to_http(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertIsNone(load_tls_settings(root,{})['certificate'])
            (root/'server-cert.pem').write_text('test')
            with self.assertRaises(RuntimeError):load_tls_settings(root,{})
            with self.assertRaises(RuntimeError):load_tls_settings(root,{'TLS_CERT_FILE':'only-cert'})

    def test_explicit_certificates_take_precedence_over_local_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('other-cert.pem','other-key.pem'):(root/name).write_text('test')
            settings=load_tls_settings(root,{'TLS_CERT_FILE':str(root/'other-cert.pem'),'TLS_KEY_FILE':str(root/'other-key.pem')})
            self.assertTrue(settings['certificate'].endswith('other-cert.pem'))
            self.assertIsNone(settings['ca'])


class CertificateDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.der=b'public-certificate-test'
        self.pem=b'-----BEGIN CERTIFICATE-----\n'+base64.b64encode(self.der)+b'\n-----END CERTIFICATE-----\n'
        self.path=Path(self.directory.name)/'maquette-ca.crt'
        self.path.write_bytes(self.pem)
        (Path(self.directory.name)/'rootCA-key.pem').write_text('PRIVATE MUST NEVER BE SERVED')
        self.client=create_certificate_app(self.path,'10.21.23.100').test_client()

    def test_download_is_only_public_certificate(self):
        response=self.client.get('/maquette-ca.crt')
        self.addCleanup(response.close)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,self.pem)
        self.assertIn('attachment',response.headers['Content-Disposition'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_private_files_and_directory_listing_are_inaccessible(self):
        for path in ('/rootCA-key.pem','/server-key.pem','/ca/rootCA-key.pem','/../rootCA-key.pem','/api/plans'):
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.post('/maquette-ca.crt').status_code,405)

    def test_page_shows_https_target_and_der_fingerprint(self):
        page=self.client.get('/').get_data(as_text=True)
        self.assertIn('https://10.21.23.100:5000',page)
        self.assertIn(certificate_fingerprint(self.path),page)
        self.assertEqual(certificate_fingerprint(self.path).replace(':',''),hashlib.sha256(self.der).hexdigest().upper())
