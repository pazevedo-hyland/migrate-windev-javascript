"""Inspect synthetic PDF bytes on stdin. Requires the starter's pinned pypdf."""
import io
import json
import sys

from pypdf import PdfReader

result = []
for page in PdfReader(io.BytesIO(sys.stdin.buffer.read())).pages:
    runs = []

    def visitor(text, matrix, text_matrix, font, size):
        x, y = text_matrix[4:6]
        runs.append({
            "text": text,
            "xMm": (x * matrix[0] + y * matrix[2] + matrix[4]) * 25.4 / 72,
            "yMm": (x * matrix[1] + y * matrix[3] + matrix[5]) * 25.4 / 72,
        })

    text = page.extract_text(visitor_text=visitor)
    fonts = [font.get_object() for font in page["/Resources"]["/Font"].values()]
    descriptors = [child.get_object().get("/FontDescriptor").get_object()
                   for font in fonts for child in font.get("/DescendantFonts", [])]
    result.append({
        "text": text,
        "runs": runs,
        "widthMm": float(page.mediabox.width) * 25.4 / 72,
        "heightMm": float(page.mediabox.height) * 25.4 / 72,
        "embeddedFonts": sum(any(key in descriptor for key in ["/FontFile", "/FontFile2", "/FontFile3"])
                             for descriptor in descriptors),
    })
print(json.dumps(result))
