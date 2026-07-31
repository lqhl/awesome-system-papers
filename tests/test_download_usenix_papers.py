import unittest

from scripts.download_usenix_papers import extract_paper_ids, pdf_filename, pdf_filename_prefix


class PdfFilenameTest(unittest.TestCase):
    def test_osdi_uses_short_year(self):
        self.assertEqual(pdf_filename("osdi", 2026, "xie-zhiqiang"), "osdi26-xie-zhiqiang.pdf")

    def test_other_usenix_conferences_keep_full_year(self):
        self.assertEqual(pdf_filename("nsdi", 2026, "smith"), "nsdi2026-smith.pdf")

    def test_osdi_prefix_is_suitable_for_globbing(self):
        self.assertEqual(pdf_filename_prefix("osdi", 2026), "osdi26-")


class ExtractPaperIdsTest(unittest.TestCase):
    def test_ignores_non_paper_presentations(self):
        page = """
        <a href="/conference/osdi26/presentation/keynote">Keynote</a>
        <a href="/conference/osdi26/presentation/xie-zhiqiang">Strata</a>
        """
        self.assertEqual(extract_paper_ids(page, "osdi", 2026), ["xie-zhiqiang"])


if __name__ == "__main__":
    unittest.main()
