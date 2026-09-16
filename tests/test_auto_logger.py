import importlib.machinery
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
loader = importlib.machinery.SourceFileLoader("auto_logger", str(ROOT / "wfweb-auto-logger"))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class AutoLoggerTests(unittest.TestCase):
    #===========================================================================
    # Verify ADIF mode normalization and frequency conversion
    #===========================================================================
    def test_adif_normalizes_submode_and_frequency(self):
        adif = module.qso_to_adif({
            "call": "w1aw", "date": "20260916", "time": "1234",
            "band": "20M", "mode": "FT4", "freq": 14080000,
            "rstSent": "-10", "rstRcvd": "-08",
        }, "kf0zjt")
        self.assertIn("<CALL:4>W1AW", adif)
        self.assertIn("<MODE:4>MFSK<SUBMODE:3>FT4", adif)
        self.assertIn("<FREQ:5>14.08", adif)

    #===========================================================================
    # Verify the original QRZ offset is retained during state migration
    #===========================================================================
    def test_legacy_state_only_migrates_qrz_offset(self):
        offsets = module.state_offsets(
            {"inode": 10, "offset": 42}, ["qrz", "eqsl"], 10, 100
        )
        self.assertEqual(offsets, {"qrz": 42, "eqsl": 100})

    #===========================================================================
    # Verify eQSL credentials and the QSO are encoded in the upload request
    #===========================================================================
    def test_eqsl_request_contains_adif_credentials(self):
        args = SimpleNamespace(
            eqsl_username="W1AW", eqsl_password="AN~bL]adv=Q2bf",
            eqsl_qth_nickname="Home",
        )
        response = mock.MagicMock()
        response.read.return_value = b"Result: 1 out of 1 records added"
        response.__enter__.return_value = response
        with mock.patch.object(module.urllib.request, "urlopen", return_value=response) as open_url:
            accepted, message = module.submit_eqsl(args, {}, "<CALL:6>KF0ZJT<EOR>")
        self.assertTrue(accepted)
        url = open_url.call_args.args[0].full_url
        self.assertIn("ImportADIF.cfm?ADIFData=", url)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        upload = query["ADIFData"][0]
        self.assertIn("<eQSL_User:4>W1AW", upload)
        self.assertIn("<eQSL_Pswd:14>AN~bL]adv=Q2bf", upload)
        self.assertIn("<QTHNickname:4>Home", upload)
        self.assertNotIn("<USERID", upload)
        self.assertNotIn("<PASSWORD", upload)
        self.assertEqual(message, "1 out of 1 records added")

    #===========================================================================
    # Verify HamQTH receives its documented form fields and ADIF field names
    #===========================================================================
    def test_hamqth_request_uses_documented_contract(self):
        args = SimpleNamespace(station_callsign="W1AW", hamqth_username="w1aw",
                               hamqth_password="secret")
        response = mock.MagicMock()
        response.read.return_value = b"QSO OK"
        response.__enter__.return_value = response
        with mock.patch.object(module.urllib.request, "urlopen",
                               return_value=response) as open_url:
            accepted, message = module.submit_hamqth(args, {
                "call": "KF0ZJT", "date": "20260916", "time": "1435",
                "freq": 14074000, "band": "20m", "mode": "FT8",
                "rstSent": "-12", "rstRcvd": "-08",
            }, "unused")
        request = open_url.call_args.args[0]
        fields = urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(fields["u"], ["w1aw"])
        self.assertEqual(fields["p"], ["secret"])
        self.assertEqual(fields["c"], ["W1AW"])
        self.assertEqual(fields["prg"], ["wfweb-auto-logger"])
        self.assertEqual(fields["cmd"], ["insert"])
        self.assertIn("<QSO_DATE:8>20260916", fields["adif"][0])
        self.assertIn("<RST_S:3>-12<RST_R:3>-08", fields["adif"][0])
        self.assertTrue(accepted)
        self.assertEqual(message, "QSO OK")

    #===========================================================================
    # Verify HamQTH HTTP rejections preserve the response body for diagnosis
    #===========================================================================
    def test_hamqth_qso_rejection_is_handled(self):
        args = SimpleNamespace(station_callsign="W1AW", hamqth_username="w1aw",
                               hamqth_password="secret")
        error = module.urllib.error.HTTPError(
            module.HAMQTH_URL, 400, "QSO Rejected", {},
            io.BytesIO(b"QSO already exists in database"),
        )
        with mock.patch.object(module.urllib.request, "urlopen", side_effect=error):
            accepted, message = module.submit_hamqth(args, {
                "call": "KF0ZJT", "date": "20260916", "time": "1435",
                "band": "20m", "mode": "FT8",
                "rstSent": "-12", "rstRcvd": "-08",
            }, "unused")
        self.assertFalse(accepted)
        self.assertEqual(message, "HTTP 400: QSO already exists in database")

    #===========================================================================
    # Verify mandatory HamQTH signal reports are checked before making a request
    #===========================================================================
    def test_hamqth_requires_both_signal_reports(self):
        args = SimpleNamespace(station_callsign="W1AW", hamqth_username="w1aw",
                               hamqth_password="secret")
        with mock.patch.object(module.urllib.request, "urlopen") as open_url:
            accepted, message = module.submit_hamqth(args, {
                "call": "KF0ZJT", "date": "20260916", "time": "1435",
                "band": "20m", "mode": "FT8", "rstSent": "-12",
            }, "unused")
        self.assertFalse(accepted)
        self.assertIn("both sent and received", message)
        open_url.assert_not_called()

    #===========================================================================
    # Verify all supported destinations are independently registered
    #===========================================================================
    def test_configured_loggers_includes_additional_services(self):
        args = SimpleNamespace(enable_qrz=True, enable_eqsl=True,
                               enable_hamqth=True, enable_wrl=True)
        self.assertEqual(set(module.configured_loggers(args)),
                         {"qrz", "eqsl", "hamqth", "wrl"})

    #===========================================================================
    # Verify World Radio League receives documented contact JSON and authentication
    #===========================================================================
    def test_wrl_request_contains_contact_and_api_key(self):
        args = SimpleNamespace(station_callsign="W1AW", wrl_api_key="wrl-key",
                               wrl_logbook_id="00000000-0000-0000-0000-000000000001",
                               verbose=False)
        response = mock.MagicMock()
        response.read.return_value = (
            b'{"data":{"id":"qso-123","enrichment":"pending"},'
            b'"meta":null,"error":null}'
        )
        response.__enter__.return_value = response
        with mock.patch.object(module.urllib.request, "urlopen",
                               return_value=response) as open_url:
            accepted, message = module.submit_wrl(args, {
                "call": "kf0zjt", "date": "20260916", "time": "1435",
                "freq": 14074000, "band": "20M", "mode": "FT8",
                "rstSent": "-12", "rstRcvd": "-08",
            }, "<CALL:6>KF0ZJT<EOR>")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url,
                         "https://api.worldradioleague.com/v1/contacts")
        self.assertEqual(json.loads(request.data),
                         {"programId": "wfweb-auto-logger",
                          "call": "KF0ZJT",
                          "timestamp": {"qsoDate": "20260916", "timeOn": "1435"},
                          "freq": 14.074, "band": "20m", "mode": "FT8",
                          "stationCallsign": "W1AW", "rstSent": "-12",
                          "rstRcvd": "-08",
                          "logbookId": "00000000-0000-0000-0000-000000000001"})
        self.assertEqual(request.get_header("Authorization"), "Bearer wrl-key")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertTrue(accepted)
        self.assertEqual(message, "created contact qso-123")

    #===========================================================================
    # Verify a documented WRL validation error is a handled record rejection
    #===========================================================================
    def test_wrl_validation_error_is_rejected(self):
        args = SimpleNamespace(station_callsign="W1AW", wrl_api_key="wrl-key",
                               wrl_logbook_id=None, verbose=False)
        body = (b'{"data":null,"meta":null,"error":'
                b'{"code":"LOGBOOK_REQUIRED","message":"Choose a logbook."}}')
        error = module.urllib.error.HTTPError(
            module.WRL_URL, 422, "Unprocessable Content", {}, io.BytesIO(body)
        )
        with mock.patch.object(module.urllib.request, "urlopen", side_effect=error):
            accepted, message = module.submit_wrl(args, {
                "call": "W1AW", "date": "20260916", "time": "1435",
                "freq": 14074000, "band": "20m", "mode": "FT8",
            }, "unused")
        self.assertFalse(accepted)
        self.assertEqual(message, "LOGBOOK_REQUIRED: Choose a logbook.")

    #===========================================================================
    # Verify WRL server errors retain diagnostic details and remain retryable
    #===========================================================================
    def test_wrl_server_error_preserves_request_id_for_retry(self):
        args = SimpleNamespace(station_callsign="W1AW", wrl_api_key="wrl-key",
                               wrl_logbook_id=None, verbose=False)
        body = (b'{"data":null,"meta":null,"error":{"code":"INTERNAL_ERROR",'
                b'"message":"Could not determine the destination logbook.",'
                b'"requestId":"379f8bce-f716-45d0-bbb8-c64193941183"}}')
        error = module.urllib.error.HTTPError(
            module.WRL_URL, 500, "Internal Server Error", {}, io.BytesIO(body)
        )
        with mock.patch.object(module.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(
                    module.TransientUploadError,
                    "INTERNAL_ERROR.*379f8bce-f716-45d0-bbb8-c64193941183.*"
                    "--wrl-logbook-id"):
                module.submit_wrl(args, {
                    "call": "W1AW", "date": "20260916", "time": "1435",
                    "freq": 14074000, "band": "20m", "mode": "FT8",
                }, "unused")

    #===========================================================================
    # Verify network errors remain pending and are not recorded as rejections
    #===========================================================================
    def test_network_failure_is_pending_without_failure_record(self):
        args = SimpleNamespace(dry_run=False, failed_file=pathlib.Path("unused"), verbose=False)
        submit = mock.Mock(side_effect=module.urllib.error.URLError("offline"))
        with mock.patch.object(module, "record_failure") as record:
            handled = module.process_for_logger(args, "eqsl", submit, {}, "<EOR>")
        self.assertFalse(handled)
        record.assert_not_called()

    #===========================================================================
    # Verify an eQSL rejection is attributed only to the eQSL logger
    #===========================================================================
    def test_rejection_is_recorded_for_only_that_logger(self):
        with tempfile.TemporaryDirectory() as directory:
            failed = pathlib.Path(directory) / "failed.jsonl"
            args = SimpleNamespace(dry_run=False, failed_file=failed, verbose=False)
            handled = module.process_for_logger(
                args, "eqsl", lambda args, qso, adif: (False, "bad login"),
                {"call": "W1AW"}, "<EOR>",
            )
            self.assertTrue(handled)
            self.assertIn('"logger":"eqsl"', failed.read_text())


if __name__ == "__main__":
    unittest.main()
