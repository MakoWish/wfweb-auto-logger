import importlib.machinery
import importlib.util
import pathlib
import tempfile
import unittest
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
            eqsl_username="W1AW", eqsl_password="secret",
            eqsl_qth_nickname="Home",
        )
        response = mock.MagicMock()
        response.read.return_value = b"Result: 1 out of 1 records added"
        response.__enter__.return_value = response
        with mock.patch.object(module.urllib.request, "urlopen", return_value=response) as open_url:
            accepted, message = module.submit_eqsl(args, "<CALL:6>KF0ZJT<EOR>")
        self.assertTrue(accepted)
        url = open_url.call_args.args[0].full_url
        self.assertIn("ImportADIF.cfm?ADIFData=", url)
        self.assertIn("USERID%3A4%3EW1AW", url)
        self.assertIn("PASSWORD%3A6%3Esecret", url)
        self.assertEqual(message, "1 out of 1 records added")

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
                args, "eqsl", lambda args, adif: (False, "bad login"),
                {"call": "W1AW"}, "<EOR>",
            )
            self.assertTrue(handled)
            self.assertIn('"logger":"eqsl"', failed.read_text())


if __name__ == "__main__":
    unittest.main()
