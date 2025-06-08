import argparse

try:
    from weasyprint import HTML
except ImportError as exc:
    raise SystemExit("weasyprint is required to convert HTML to PDF") from exc


def convert_html_to_pdf(html_path: str, pdf_path: str) -> None:
    """Convert an HTML file to PDF using WeasyPrint."""
    HTML(html_path).write_pdf(pdf_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert HTML report to PDF")
    parser.add_argument("html", help="Input HTML report")
    parser.add_argument("output", nargs="?", default="report.pdf", help="PDF output path")
    args = parser.parse_args()
    convert_html_to_pdf(args.html, args.output)


if __name__ == "__main__":
    main()
